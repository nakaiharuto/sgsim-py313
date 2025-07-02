import socket
import threading
import json
import random

HOST = '0.0.0.0'
PORT = 8000

# ランダムなノード情報を生成
def random_mv(length=32):
    return ''.join(random.choice('01') for _ in range(length))

node_info = {
    "key": random.randint(0, 1000),
    "mv": random_mv(),
    "neighbors": []  # ← 将来は実際のSkipGraph情報を入れる
}

def handle_client(conn, addr):
    with conn:
        data = conn.recv(1024).decode()
        try:
            req = json.loads(data)
            if req["cmd"] == "get_status":
                conn.sendall(json.dumps(node_info).encode())
            else:
                conn.sendall(b'{"result": "unknown command"}')
        except Exception as e:
            conn.sendall(json.dumps({"error": str(e)}).encode())

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Node server started on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    run_server()
