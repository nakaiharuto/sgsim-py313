import socket
import json
import matplotlib.pyplot as plt

NODES = [
    ("192.168.1.101", 8000),  # Pi1
    ("192.168.1.102", 8000),  # Pi2
    ("192.168.1.103", 8000),  # Pi3
]

def get_node_status(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=2) as s:
            s.sendall(b'{"cmd":"get_status"}')
            data = s.recv(4096)
            return json.loads(data)
    except Exception as e:
        return {"error": str(e)}

def main():
    infos = []
    for ip, port in NODES:
        status = get_node_status(ip, port)
        print(f"Node {ip}:{port} → {status}")
        infos.append(status)
    # 可視化例（keyをx軸にして並べるだけのシンプルな図）
    keys = [info.get('key', 0) for info in infos]
    plt.bar(range(len(keys)), keys, tick_label=[f"Node{i}" for i in range(len(keys))])
    plt.xlabel("Node")
    plt.ylabel("Key value")
    plt.title("SkipGraph Node Keys")
    plt.show()

if __name__ == "__main__":
    main()
