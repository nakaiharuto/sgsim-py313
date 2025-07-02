import socket
import threading
import time
import random
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ノード情報（自動生成）
NODE_KEY = random.randint(100, 999)
NODE_MV = ''.join(str(random.randint(0, 1)) for _ in range(32))
NEIGHBORS = []

# UDPブロードキャストで「誰かいますか？」を送信
def broadcast_discover():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"SGDISCOVER:{NODE_KEY}".encode()
    while True:
        sock.sendto(msg, ('<broadcast>', 12000))
        time.sleep(3)

# UDPで「います！」と返事
def listen_discover():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 12000))
    while True:
        data, addr = sock.recvfrom(1024)
        if data.startswith(b"SGDISCOVER"):
            # 自分以外なら返事
            their_key = int(data.decode().split(":")[1])
            if their_key != NODE_KEY:
                reply = f"SGREPLY:{NODE_KEY}:{NODE_MV}".encode()
                sock.sendto(reply, addr)

# UDPでreplyを受け取ったらneighbor追加
def listen_reply():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 12001))
    while True:
        data, addr = sock.recvfrom(1024)
        if data.startswith(b"SGREPLY"):
            parts = data.decode().split(":")
            neighbor_key = int(parts[1])
            neighbor_mv = parts[2]
            neighbor_ip = addr[0]
            neighbor = {"key": neighbor_key, "mv": neighbor_mv, "ip": neighbor_ip}
            if neighbor not in NEIGHBORS and neighbor_key != NODE_KEY:
                NEIGHBORS.append(neighbor)
                print(f"NEW neighbor discovered: {neighbor}")

# 自分の状態を返す簡易HTTPサーバ
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = json.dumps({"key": NODE_KEY, "mv": NODE_MV, "neighbors": NEIGHBORS})
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(body.encode())

def run_http():
    httpd = HTTPServer(("", 8000), Handler)
    httpd.serve_forever()

if __name__ == "__main__":
    print(f"My Node Key: {NODE_KEY}")
    # スレッドでブロードキャスト＆リスナ起動
    threading.Thread(target=broadcast_discover, daemon=True).start()
    threading.Thread(target=listen_discover, daemon=True).start()
    threading.Thread(target=listen_reply, daemon=True).start()
    run_http()
