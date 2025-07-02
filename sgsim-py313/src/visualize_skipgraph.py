import requests
import sg
import matplotlib.pyplot as plt

# ===== 設定 =====
NODE_IPS = [
    "10.205.109.98:8000",  # ラズパイ1号
    # 必要なら他ノードのIP:PORTも追加
]

def fetch_node_info(node_addr):
    url = f"http://{node_addr}/"
    print("GET:", url)
    try:
        resp = requests.get(url, timeout=3)
        info = resp.json()
        print("RECV:", info)
        # ここが重要！！mvは文字列→int(ALPHA進数)でMembershipVectorへ
        mv_str = info.get("mv")
        if mv_str is None:
            raise ValueError("Missing 'mv' in response")
        mv_int = int(mv_str, sg.ALPHA)
        mv = sg.MembershipVector(mv_int)
        node = sg.SGNode(info["key"], mv)
        node.status = info.get("status", "unknown")
        node.neighbor_keys = info.get("neighbors", [])
        return node
    except Exception as e:
        print(f"FAILED to fetch node info from {node_addr}: {e}")
        return None

def main():
    nodes = []
    for addr in NODE_IPS:
        node = fetch_node_info(addr)
        if node:
            nodes.append(node)

    if not nodes:
        print("ノード情報が取得できませんでした。")
        return

    # --- 可視化：超シンプルver ---
    # keyをx、node順をyとしてプロット（隣接ノード線も引く）

    plt.figure(figsize=(8, 2))
    for i, node in enumerate(nodes):
        plt.plot(node.key, 1, "o", label=f"N{node.key}")
        for nkey in getattr(node, "neighbor_keys", []):
            # 隣接ノードへの線を引く
            plt.plot([node.key, nkey], [1, 1], "k--", lw=0.7)

    plt.yticks([])
    plt.xlabel("Key")
    plt.title("Skip Graph (node visualization)")
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
