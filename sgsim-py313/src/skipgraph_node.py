import socket
import threading
import time
import random
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

NODE_KEY = random.randint(100, 999)
NODE_MV = ''.join(str(random.randint(0, 1)) for _ in range(32))
NEIGHBORS = []

# UDPブロードキャスト: 自分を定期アナウンス
def broadcast_presence():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"SGNODE:{NODE_KEY}:{NODE_MV}".encode()
    while True:
        sock.sendto(msg, ('<broadcast>', 9876))
        time.sleep(2)

# HTTPサーバ（可視化ツールからGETでアクセスされる）
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
    print("My Node Key:", NODE_KEY)
    threading.Thread(target=broadcast_presence, daemon=True).start()
    run_http()
