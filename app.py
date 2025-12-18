from flask import Flask, render_template, jsonify, request
from pythonping import ping
import threading
import time
import json
import os


app = Flask(__name__)
data = {}
threads = {}
lock = threading.Lock()
MAX_HOSTS = 60
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(BASE_DIR, 'hosts.json')


def start_saved_hosts():
    hosts = load_hosts()

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


def load_hosts():
    if not os.path.exists(HOSTS_FILE):
        return []
    with open(HOSTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_hosts(hosts):
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(hosts, f, indent=2, ensure_ascii=False)


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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/add_ip', methods=['POST'])
def add_ip():
    payload = request.json
    ip = payload.get('ip')
    name = payload.get('name')

    if not ip:
        return jsonify({"status": "error", "msg": "IP inválido"}), 400

    hosts = load_hosts()

    if len(hosts) >= MAX_HOSTS and not any(h["ip"] == ip for h in hosts):
        return jsonify({
            "status": "error",
            "msg": f"Limite máximo de {MAX_HOSTS} IPs atingido"
        }), 400

    if not any(h["ip"] == ip for h in hosts):
        hosts.append({
            "ip": ip,
            "name": name or ip
        })
        save_hosts(hosts)

    if ip not in threads:
        t = threading.Thread(
            target=monitor_ip,
            args=(ip,),
            daemon=True
        )
        threads[ip] = t
        t.start()

    return jsonify({"status": "ok"})


@app.route('/data')
def get_data():
    with lock:
        return jsonify(data)


@app.route('/hosts')
def get_hosts():
    return jsonify(load_hosts())


@app.route('/remove_ip', methods=['POST'])
def remove_ip():
    ip = request.json.get('ip')

    if not ip:
        return jsonify({"status": "error"}), 400

    # remove do arquivo
    hosts = load_hosts()
    hosts = [h for h in hosts if h["ip"] != ip]
    save_hosts(hosts)

    # remove dados em memória
    with lock:
        data.pop(ip, None)

    threads.pop(ip, None)

    return jsonify({"status": "ok"})


if __name__ == '__main__':
    start_saved_hosts()
    app.run(debug=True)
