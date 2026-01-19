from flask import Flask, render_template, jsonify, request, g
from flask import session, redirect, url_for, abort
from functools import wraps
from pythonping import ping
from werkzeug.security import generate_password_hash, check_password_hash
import pystray
from pystray import MenuItem as item
from PIL import Image
import webbrowser
import threading
import time
import sqlite3
import os
import sys
# import secrets


app = Flask(__name__)
app.secret_key = "nz1zbil0039bm7tgs73dh260k7fvnv53"

# =========================
# CONFIG
# =========================


def get_base_dir():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)  # pasta do .exe
    return os.path.dirname(os.path.abspath(__file__))


# CONFIG NO .EXE
BASE_DIR = get_base_dir()
DB_PATH = os.path.join(BASE_DIR, "data", "ping_monitor.db")

# CONFIG EM DEV
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_PATH = os.path.join(BASE_DIR, "data", "ping_monitor.db")

MAX_HOSTS = 60

# =========================
# SYSTRAY ICON
# =========================


def on_exit(icon, item):
    icon.stop()
    os._exit(0)


def create_tray_icon():
    icon_image = Image.new('RGB', (64, 64), color=(0, 128, 0))  # verde padrão
    menu = (item('Abrir', lambda: webbrowser.open("http://127.0.0.1:5000")),
            item('Sair', on_exit))
    icon = pystray.Icon("PingMonitor", icon_image, "Ping Monitor", menu)
    icon.run()


# =========================
# RUNTIME STATE
# =========================
data = {}

threads = {}

lock = threading.Lock()

# =========================
# LOGIN
# =========================


def login_required(role=None):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper

# =========================
# LOGS AUTOMATIZADOS
# =========================


def log_action(action, target=None):
    try:
        user = session.get("user")
        db = get_db()
        db.execute(
            "INSERT INTO logs (user, action, target) VALUES (?, ?, ?)",
            (user, action, target)
        )
        db.commit()
    except Exception:
        pass


# =========================
# DB
# =========================


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db:
        db.close()

# =========================
# MONITOR
# =========================


def calculate_status(history):
    last = history[-3:]

    if any(h["loss"] == 100 for h in last):
        return "DOWN"
    if any(h["loss"] > 0 for h in last):
        return "INSTAVEL"
    return "UP"


def monitor_ip(ip):
    while True:
        try:
            response = ping(ip, count=5, timeout=1)
            latency = response.rtt_avg_ms if response.success() else None

            sent = len(response._responses)
            received = sum(1 for r in response._responses if r.success)
            loss = 100 * (sent - received) / sent if sent > 0 else 100

        except Exception:
            latency = None
            loss = 100

        with lock:
            data.setdefault(ip, [])

            entry = {
                "ts": int(time.time()),
                "latency": latency,
                "loss": loss,
                "status": None
            }

            data[ip].append(entry)
            data[ip] = data[ip][-50:]
            entry["status"] = calculate_status(data[ip])

        time.sleep(2)

# =========================
# START SAVED HOSTS
# =========================


def start_saved_hosts():
    print("🔄 Carregando hosts do banco...")
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.execute("SELECT host FROM hosts WHERE active = 1")
    rows = cur.fetchall()
    print("Hosts encontrados:", [row["host"] for row in rows])
    db.close()

    for row in rows:
        ip = row["host"]
        print("▶ Iniciando monitor para:", ip)

        if ip not in threads:
            t = threading.Thread(
                target=monitor_ip,
                args=(ip,),
                daemon=True
            )
            threads[ip] = t
            t.start()


# =========================
# ROUTES
# =========================

# -------- GROUPS --------
@app.route("/hosts/groups")
def get_groups():
    db = get_db()
    cur = db.execute("""
        SELECT group_name, host, label
        FROM hosts
        WHERE active = 1
        ORDER BY group_name
    """)

    groups = {}
    for row in cur.fetchall():
        groups.setdefault(row["group_name"], []).append({
            "ip": row["host"],
            "name": row["label"]
        })

    return jsonify({"groups": groups})


@app.route("/groups/add", methods=["POST"])
def add_group():
    name = request.json.get("name")
    if not name:
        return jsonify({"status": "error"}), 400
    return jsonify({"status": "ok"})


@app.route("/groups/remove", methods=["POST"])
def remove_group():
    name = request.json.get("name")
    if not name:
        return jsonify({"status": "error"}), 400

    db = get_db()
    db.execute("DELETE FROM hosts WHERE group_name = ?", (name,))
    db.commit()

    return jsonify({"status": "ok"})

# -------- HOSTS --------


@app.route("/add_ip", methods=["POST"])
def add_ip():
    payload = request.json
    ip = payload.get("ip")
    name = payload.get("name")
    group = payload.get("group")

    if not ip or not group:
        return jsonify({"status": "error"}), 400

    db = get_db()

    cur = db.execute("SELECT COUNT(*) FROM hosts WHERE active = 1")
    total = cur.fetchone()[0]

    if total >= MAX_HOSTS:
        return jsonify({
            "status": "error",
            "msg": f"Limite máximo de {MAX_HOSTS} IPs atingido"
        }), 400

    db.execute("""
        INSERT INTO hosts (group_name, host, label)
        VALUES (?, ?, ?)
    """, (group, ip, name or ip))

    db.commit()

    if ip not in threads:
        t = threading.Thread(
            target=monitor_ip,
            args=(ip,),
            daemon=True
        )
        threads[ip] = t
        t.start()

    return jsonify({"status": "ok"})


@app.route("/remove_ip", methods=["POST"])
def remove_ip():
    ip = request.json.get("ip")
    if not ip:
        return jsonify({"status": "error"}), 400

    db = get_db()
    db.execute("DELETE FROM hosts WHERE host = ?", (ip,))
    db.commit()

    with lock:
        data.pop(ip, None)

    threads.pop(ip, None)

    return jsonify({"status": "ok"})

# -------- DATA --------


@app.route("/data")
def get_data():
    print("DATA KEYS:", list(data.keys()))
    with lock:
        return jsonify(data)


# -------- LOGIN/LOGOUT --------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        cur = db.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ? AND active = 1",
            (username,)
        )
        user = cur.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            log_action("LOGIN", user["username"])
            return redirect(url_for("index"))

        return render_template("login.html", error="Usuário ou senha inválidos")

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_action("LOGOUT", session["user"])
    session.clear()
    return redirect(url_for("login"))

# -------- APP PROTEGIDO --------


@app.route("/")
@login_required()
def index():
    return render_template("index.html")


@app.route("/users", methods=["GET", "POST"])
@login_required(role="admin")
def users():
    db = get_db()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if not username or not password or not role:
            return "Dados inválidos", 400

        password_hash = generate_password_hash(password)

        db.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (username, password_hash, role))
        db.commit()

        log_action("CREATE_USER", username)

        return redirect(url_for("users"))

    cur = db.execute("SELECT username, role, active FROM users")
    users = cur.fetchall()

    return render_template("users.html", users=users)


# =========================
# MAIN
# =========================

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")

# if __name__ == "__main__":
#    start_saved_hosts()
#    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_saved_hosts()

    threading.Thread(target=open_browser, daemon=True).start()
    threading.Thread(target=create_tray_icon, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
