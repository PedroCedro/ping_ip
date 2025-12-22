from flask import Flask, render_template, jsonify, request
from pythonping import ping
import threading
import time
import json
import os

app = Flask(__name__)

# =========================
# GLOBALS
# =========================
data = {}          # histórico de ping (runtime)
threads = {}       # threads por IP
lock = threading.Lock()

MAX_HOSTS = 60
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(BASE_DIR, 'hosts.json')


# =========================
# HOSTS LOAD / SAVE
# =========================
def load_hosts(flat=True):
    if not os.path.exists(HOSTS_FILE):
        return [] if flat else {"groups": {}}

    with open(HOSTS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # MODELO ANTIGO → migração automática
    if isinstance(raw, list):
        raw = {
            "groups": {
                "Geral": {
                    "order": 1,
                    "hosts": raw
                }
            }
        }

    if flat:
        hosts = []
        for group in raw["groups"].values():
            hosts.extend(group["hosts"])
        return hosts

    return raw


def save_hosts(data):
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =========================
# START SAVED HOSTS
# =========================
def start_saved_hosts():
    hosts = load_hosts(flat=True)

    for h in hosts:
        ip = h["ip"]

        if ip not in threads:
            t = threading.Thread(
                target=monitor_ip,
                args=(ip,),
                daemon=True
            )
            threads[ip] = t
            t.start()


# =========================
# STATUS
# =========================
def calculate_status(history):
    last = history[-3:]

    if any(h["loss"] == 100 for h in last):
        return "DOWN"

    if any(h["loss"] > 0 for h in last):
        return "INSTAVEL"

    return "UP"


# =========================
# MONITOR
# =========================
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
# ROUTES
# =========================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/hosts')
def get_hosts():
    # frontend atual espera lista plana
    return jsonify(load_hosts(flat=True))


@app.route('/hosts/groups')
def get_hosts_groups():
    return jsonify(load_hosts(flat=False))


@app.route('/add_ip', methods=['POST'])
def add_ip():
    payload = request.json
    ip = payload.get('ip')
    name = payload.get('name')
    group_name = payload.get('group')

    if not ip or not group_name:
        return jsonify({"status": "error"}), 400

    config = load_hosts(flat=False)

    if group_name not in config["groups"]:
        return jsonify({"status": "group_not_found"}), 400

    # lista plana para validações
    flat_hosts = load_hosts(flat=True)

    if len(flat_hosts) >= MAX_HOSTS and not any(h["ip"] == ip for h in flat_hosts):
        return jsonify({
            "status": "error",
            "msg": f"Limite máximo de {MAX_HOSTS} IPs atingido"
        }), 400

    group = config["groups"][group_name]

    if not any(h["ip"] == ip for h in group["hosts"]):
        group["hosts"].append({
            "ip": ip,
            "name": name or ip
        })
        save_hosts(config)

    # inicia monitoramento
    if ip not in threads:
        t = threading.Thread(
            target=monitor_ip,
            args=(ip,),
            daemon=True
        )
        threads[ip] = t
        t.start()

    return jsonify({"status": "ok"})


@app.route('/remove_ip', methods=['POST'])
def remove_ip():
    ip = request.json.get('ip')

    if not ip:
        return jsonify({"status": "error"}), 400

    config = load_hosts(flat=False)

    for group in config["groups"].values():
        group["hosts"] = [h for h in group["hosts"] if h["ip"] != ip]

    save_hosts(config)

    with lock:
        data.pop(ip, None)

    threads.pop(ip, None)

    return jsonify({"status": "ok"})


@app.route('/data')
def get_data():
    with lock:
        return jsonify(data)

# Add Grupo


@app.route('/groups/add', methods=['POST'])
def add_group():
    name = request.json.get('name')

    if not name:
        return jsonify({"status": "error"}), 400

    data = load_hosts(flat=False)

    if name in data["groups"]:
        return jsonify({"status": "exists"}), 200

    data["groups"][name] = {
        "order": len(data["groups"]) + 1,
        "hosts": []
    }

    save_hosts(data)
    return jsonify({"status": "ok"})

# Remove Grupo


@app.route('/groups/remove', methods=['POST'])
def remove_group():
    name = request.json.get('name')

    if not name:
        return jsonify({"status": "error"}), 400

    data = load_hosts(flat=False)

    if name in data["groups"]:
        del data["groups"][name]
        save_hosts(data)

    return jsonify({"status": "ok"})


# =========================
# MAIN
# =========================
if __name__ == '__main__':
    start_saved_hosts()
    app.run(debug=True)
