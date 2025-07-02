import socket
import threading
import time
import requests
import json
import matplotlib.pyplot as plt

LEVELS = 4
DISCOVERED_NODES = {}

def listen_for_nodes(port=12000):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', port))
    while True:
        msg, addr = s.recvfrom(1024)
        try:
            info = json.loads(msg.decode())
            ip = addr[0]
            DISCOVERED_NODES[ip] = info
        except Exception:
            continue

def fetch_node_info(ip):
    url = f"http://{ip}:8000/"
    try:
        resp = requests.get(url, timeout=2)
        return resp.json()
    except Exception:
        return None

def plot_skipgraph(nodes):
    plt.clf()
    y = 1
    for node in nodes:
        x = node['key']
        plt.plot(x, y, "o", label=f"N{x}")
        for neighbor in node.get('neighbors', []):
            for l in ['LEFT', 'RIGHT']:
                for nkey in neighbor[l]:
                    plt.plot([x, nkey], [y, y], "k--", lw=0.7)
    plt.yticks([])
    plt.xlabel("Key")
    plt.title("SkipGraph(UDP/HTTP)")
    plt.legend()
    plt.tight_layout()
    plt.pause(0.1)

if __name__ == "__main__":
    print("動的探索モードでSkipGraphノードを可視化します")
    threading.Thread(target=listen_for_nodes, daemon=True).start()

    plt.ion()  # インタラクティブ
    plt.figure(figsize=(7, 2))
    try:
        while True:
            ips = list(DISCOVERED_NODES.keys())
            nodes = []
            for ip in ips:
                info = fetch_node_info(ip)
                if info:
                    nodes.append(info)
            if nodes:
                plot_skipgraph(nodes)
            time.sleep(2)
    except KeyboardInterrupt:
        print("終了")
