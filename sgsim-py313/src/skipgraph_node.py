#ノード立ち上げコード
import socket
import threading
import time
import random
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

LEVELS = 4        # 本番は32推奨。デモなら見やすく4くらいで。
ALPHA = 2         # MembershipVectorの基数（2進数）
MV_LEN = 32

def random_mv(length=MV_LEN, alpha=ALPHA):
    return ''.join(str(random.randint(0, alpha-1)) for _ in range(length))

# ---- ノード情報 ----
NODE_KEY = random.randint(100, 999)
NODE_MV = random_mv()
ALL_NODES = {}   # {ip: {"key": ..., "mv": ...}}

def common_prefix(a, b):
    """2進数文字列の共通接頭辞長さ"""
    return sum(x == y for x, y in zip(a, b))

# ---- UDPブロードキャストでノード発見 ----
def udp_discovery():
    # 送信側
    def broadcaster():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = json.dumps({"key": NODE_KEY, "mv": NODE_MV}).encode()
        while True:
            sock.sendto(msg, ('10.205.127.255', 12000))  # ここを修正！
            time.sleep(2)
    # 受信側
    def listener():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 12000))
        while True:
            data, addr = sock.recvfrom(1024)
            try:
                info = json.loads(data.decode())
                ip = addr[0]
                if ip == get_my_ip():
                    continue
                if ip not in ALL_NODES:
                    print(f"[discovered] {ip}: {info}")
                ALL_NODES[ip] = info
            except Exception:
                pass
    threading.Thread(target=broadcaster, daemon=True).start()
    threading.Thread(target=listener, daemon=True).start()

def get_my_ip():
    # 適当な方法で自分のIP取得
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def calc_neighbors():
    """各levelごとにLEFT/RIGHTを計算して返す"""
    my_key = NODE_KEY
    my_mv = NODE_MV
    # 自分も含める
    all_nodes = list(ALL_NODES.values()) + [{"key": my_key, "mv": my_mv}]
    neighbors = []
    for level in range(LEVELS):
        same_prefix = [
            n for n in all_nodes
            if common_prefix(my_mv, n['mv']) >= level + 1 and n['key'] != my_key
        ]
        left = None
        right = None
        lefts = [n for n in same_prefix if n['key'] < my_key]
        rights = [n for n in same_prefix if n['key'] > my_key]
        if lefts:
            left = max(lefts, key=lambda n: n['key'])['key']
        if rights:
            right = min(rights, key=lambda n: n['key'])['key']
        neighbors.append({
            "level": level,
            "LEFT": [left] if left is not None else [],
            "RIGHT": [right] if right is not None else []
        })
    return neighbors

# ---- HTTPサーバ（/ で状態返す） ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            neighbors = calc_neighbors()
            body = json.dumps({
                "key": NODE_KEY,
                "mv": NODE_MV,
                "neighbors": neighbors,
            })
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(body.encode())

def run_http():
    httpd = HTTPServer(("", 8000), Handler)
    print(f"HTTP server on {get_my_ip()}:8000 (key={NODE_KEY})")
    httpd.serve_forever()

if __name__ == "__main__":
    print(f"Start Node: key={NODE_KEY}, mv={NODE_MV}, ip={get_my_ip()}")
    udp_discovery()
    run_http()
