import socket, threading, time, requests, json
import matplotlib.pyplot as plt
import sg_draw
import sg                          # sg_draw が参照するので import 必須
from realtime_node import RealNode  # ← 作ったやつ

LEVELS = 4
# ★ IPだけでなく (IP, PORT) をキーにする
DISCOVERED_NODES = {}   # type: dict[tuple[str, int], dict]


# ---- 経路計算ヘルパ ----
def greedy_route(nmap, src, dst):
    if src not in nmap or dst not in nmap:
        return []
    path = [src]
    cur = src
    visited = {src}
    while cur != dst:
        best = None
        best_d = abs(dst - cur)
        cur_info = nmap.get(cur)
        if not cur_info:
            break
        for nb in cur_info["neighbors"]:
            for side in ("LEFT", "RIGHT"):
                for k in nb[side]:
                    if k is None or k in visited or k not in nmap:
                        continue
                    d = abs(dst - k)
                    if d < best_d:
                        best_d = d
                        best = k
        if best is None:
            break
        visited.add(best)
        path.append(best)
        cur = best
    return path


def find_level_between(nmap, a, b):
    for nb in nmap.get(a, {}).get("neighbors", []):
        if b in nb["LEFT"] or b in nb["RIGHT"]:
            return nb["level"]
    return 0


def listen_for_nodes(port=12000):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', port))
    while True:
        msg, addr = s.recvfrom(1024)
        try:
            info = json.loads(msg.decode())
            node_port = info.get("port", 8000)   # ★ 送られてきたポートを使う
            DISCOVERED_NODES[(addr[0], node_port)] = info   # ★ (IP,PORT) で保存
        except Exception:
            pass


# ★ (ip, port) タプルを受け取る
def fetch_node_info(ip_port):
    ip, port = ip_port
    try:
        r = requests.get(f"http://{ip}:{port}/", timeout=1.5)
        data = r.json()
        # 可視化では使わないがデバッグ用に仕込んでおく
        data["_ip"] = ip
        data["_port"] = port
        return data
    except Exception:
        return None


def plot_skipgraph(ax, nodes_json):
    ax.clear()
    if not nodes_json:
        ax.text(0.5, 0.5, "no nodes yet", transform=ax.transAxes,
                ha="center", va="center")
        return

    # JSON -> RealNode
    rnodes = [RealNode(n["key"], n["mv"], n["neighbors"]) for n in nodes_json]
    max_lvl = max((max([nb["level"] for nb in n["neighbors"]], default=0)
                   for n in nodes_json), default=0)

    labels, pos = sg_draw.render_topology_base(ax, rnodes, max_lvl)

    # --------- 経路線 ---------
    nmap = {n["key"]: n for n in nodes_json}
    if len(nmap) >= 2:
        src_key = min(nmap)
        dst_key = max(nmap)
        route = greedy_route(nmap, src_key, dst_key)
        print("keys:", sorted(nmap))
        print("route:", route)

        if len(route) >= 2:
            for a, b in zip(route, route[1:]):
                lvl = find_level_between(nmap, a, b)
                an, bn = f"{a}@{lvl}", f"{b}@{lvl}"
                if an not in pos or bn not in pos:
                    for cand in range(max_lvl + 1):
                        an, bn = f"{a}@{cand}", f"{b}@{cand}"
                        if an in pos and bn in pos:
                            break
                if an in pos and bn in pos:
                    ax.plot([pos[an][0], pos[bn][0]],
                            [pos[an][1], pos[bn][1]],
                            color='orange', lw=2, zorder=5)
            ax.text(0, max(y for (_, y) in pos.values()),
                    f"{src_key}->{dst_key}", color="magenta")
    # ---------------------------------

    ax.figure.canvas.draw_idle()
    plt.pause(0.1)


if __name__ == "__main__":
    print("動的探索モードでSkipGraphノードを可視化します")
    threading.Thread(target=listen_for_nodes, daemon=True).start()

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 7.5))

    try:
        while True:
            nodes = []
            # ★ (ip, port) ごとに取ってくる
            for ip_port in list(DISCOVERED_NODES.keys()):
                info = fetch_node_info(ip_port)
                if info:
                    nodes.append(info)

            # ★ key が重複していたら後勝ちなので、一応ユニーク化（不要なら消してOK）
            uniq = []
            seen = set()
            for n in nodes:
                if n["key"] in seen:
                    continue
                seen.add(n["key"])
                uniq.append(n)
            nodes = uniq

            plot_skipgraph(ax, nodes)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("終了")
