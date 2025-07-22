import socket, threading, time, requests, json
import matplotlib.pyplot as plt
import sg_draw
import sg                          # sg_draw が参照するので import 必須
from realtime_node import RealNode  # ← 作ったやつ

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
            DISCOVERED_NODES[addr[0]] = info
        except Exception:
            pass

def fetch_node_info(ip):
    try:
        r = requests.get(f"http://{ip}:8000/", timeout=1.5)
        return r.json()
    except Exception:
        return None

# ---------- ここがポイント ----------
def plot_skipgraph(ax, nodes_json):
    ax.clear()

    if not nodes_json:
        ax.text(0.5, 0.5, "no nodes yet", transform=ax.transAxes,
                ha="center", va="center")
        return

    # JSON → RealNode
    rnodes = [RealNode(n["key"], n["mv"], n["neighbors"]) for n in nodes_json]

    # 表示レベル算出
    max_lvl = 0
    for n in nodes_json:
        if n["neighbors"]:
            max_lvl = max(max_lvl, max(nb["level"] for nb in n["neighbors"]))

    # sg_draw の描画をそのまま使う
    sg_draw.render_topology_base(ax, rnodes, max_lvl)

    # 再描画
    ax.figure.canvas.draw_idle()
    ax.figure.canvas.flush_events()
# -----------------------------------

if __name__ == "__main__":
    print("動的探索モードでSkipGraphノードを可視化します")
    threading.Thread(target=listen_for_nodes, daemon=True).start()

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 7.5))

    try:
        while True:
            nodes = []
            for ip in list(DISCOVERED_NODES.keys()):
                info = fetch_node_info(ip)
                if info:
                    nodes.append(info)
            plot_skipgraph(ax, nodes)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("終了")
