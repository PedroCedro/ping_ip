from flask import Flask, render_template, jsonify, request, g
from flask import session, redirect, url_for, abort
from functools import wraps
from pythonping import ping
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import sqlite3
import os
import secrets



app = Flask(__name__)
app.secret_key = "nz1zbil0039bm7tgs73dh260k7fvnv53"

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "ping_monitor.db")

MAX_HOSTS = 60

# =========================
# RUNTIME STATE
# =========================
data = {}          # histórico de ping (em memória)
threads = {}       # threads por IP
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
    db = sqlite3.connect(DB_PATH)
    cur = db.execute("SELECT host FROM hosts WHERE active = 1")
    hosts = [row["host"] for row in cur.fetchall()]
    db.close()

    for ip in hosts:
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


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    start_saved_hosts()
    app.run(debug=True)
