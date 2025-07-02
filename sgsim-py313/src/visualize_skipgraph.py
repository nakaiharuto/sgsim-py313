#実ノード可視化コード
import socket
import threading
import time
import requests
import json
import sys

LEVELS = 4   # ノード側と揃えて（32推奨・デモなら4）

DISCOVERED_NODES = {}  # {ip: {"key":..., "mv":..., "neighbors":[...]}}

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

# ノード情報取得（HTTP GET）
def fetch_node_info(ip):
    url = f"http://{ip}:8000/"
    try:
        resp = requests.get(url, timeout=2)
        return resp.json()
    except Exception as e:
        return None

def print_skipgraph(nodes):
    print("=== SkipGraph Nodes ===")
    for n in nodes:
        print(f"node[{n['key']}] (mv={n['mv']})")
        for neighbor in n.get('neighbors', []):
            l = neighbor['level']
            lefts = neighbor['LEFT']
            rights = neighbor['RIGHT']
            print(f"  Level {l}: LEFT={['N'+str(k) for k in lefts]} RIGHT={['N'+str(k) for k in rights]}")
        uniq = set()
        for neighbor in n.get('neighbors', []):
            uniq.update(neighbor['LEFT'])
            uniq.update(neighbor['RIGHT'])
        uniq.discard(None)
        print(f"  # of unique nodes: {len([u for u in uniq if u is not None])}")
    print()

if __name__ == "__main__":
    print("Searching for SkipGraph nodes on UDP:12000 ...")
    threading.Thread(target=listen_for_nodes, daemon=True).start()
    time.sleep(3)   # ノードを探索する猶予（適宜調整）

    ips = list(DISCOVERED_NODES.keys())
    if not ips:
        print("ノードが見つかりませんでした。")
        sys.exit(1)
    print("Found nodes: ", ips)

    # 各ノードにHTTPで問い合わせ
    nodes = []
    for ip in ips:
        info = fetch_node_info(ip)
        if info:
            nodes.append(info)
        else:
            print(f"FAILED to fetch node info from {ip}:8000")

    if not nodes:
        print("どのノードからも情報が取れませんでした。")
        sys.exit(1)

    print_skipgraph(nodes)

    # （Optional）matplotlibでサークルプロットもOK
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(7, 2))
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
        plt.title("SkipGraph可視化 (UDP/HTTP)")
        plt.legend()
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("matplotlib未インストールのためグラフ化はスキップ")
