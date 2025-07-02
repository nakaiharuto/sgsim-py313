import socket
import threading
import time
import requests
import sg
import matplotlib.pyplot as plt

DISCOVERED_NODES = {}  # {ip: key}

# UDPでノード発見
def listen_for_nodes(port=9876):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', port))
    while True:
        msg, addr = s.recvfrom(1024)
        if msg.startswith(b'SGNODE:'):
            parts = msg.decode().split(":")
            key = int(parts[1])
            mv = parts[2]
            ip = addr[0]
            DISCOVERED_NODES[ip] = {"key": key, "mv": mv}

threading.Thread(target=listen_for_nodes, daemon=True).start()

def fetch_node_info(ip):
    url = f"http://{ip}:8000/"
    print("GET:", url)
    try:
        resp = requests.get(url, timeout=2)
        info = resp.json()
        print("RECV:", info)
        mv_str = info.get("mv")
        mv_int = int(mv_str, sg.ALPHA)
        mv = sg.MembershipVector(mv_int)
        node = sg.SGNode(info["key"], mv)
        node.status = info.get("status", "unknown")
        node.neighbor_keys = info.get("neighbors", [])
        return node
    except Exception as e:
        print(f"FAILED to fetch node info from {ip}: {e}")
        return None

while True:
    ips = list(DISCOVERED_NODES.keys())
    print("現在見つけたノード: ", ips)
    nodes = []
    for ip in ips:
        node = fetch_node_info(ip)
        if node:
            nodes.append(node)

    if nodes:
        plt.figure(figsize=(8, 2))
        for i, node in enumerate(nodes):
            plt.plot(node.key, 1, "o", label=f"N{node.key}")
            for nkey in getattr(node, "neighbor_keys", []):
                plt.plot([node.key, nkey], [1, 1], "k--", lw=0.7)
        plt.yticks([])
        plt.xlabel("Key")
        plt.title("Skip Graph (node visualization)")
        plt.legend()
        plt.tight_layout()
        plt.show()
    else:
        print("ノード情報が取得できませんでした。")
    time.sleep(10)
