import socket
import json
import random

HOST = ''
PORT = 8000

def random_mv(length=32, alpha=2):
    # 例：2進数なら"011010..."
    return ''.join(str(random.randint(0, alpha-1)) for _ in range(length))

key = random.randint(0, 1000)
mv = random_mv(32, 2)

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Node server started on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                request = conn.recv(1024)
                node_info = {
                    "key": key,
                    "mv": mv,
                    "neighbors": [],   # とりあえず空リスト
                    "status": "active"
                }
                response_body = json.dumps(node_info)
                response = (
                    "HTTP/1.0 200 OK\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    "Content-Type: application/json\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{response_body}"
                )
                conn.sendall(response.encode())

if __name__ == "__main__":
    run_server()
