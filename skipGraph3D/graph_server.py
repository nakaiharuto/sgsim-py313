import asyncio
import websockets
import json
import random
import math
 
def create_cylindrical_graph_data():
    """
    ノードを円筒・階層型に配置し、一本の連続した経路を持つデータを生成する関数。
    """
    nodes = []
    
    # --- レイアウト設定 ---
    num_levels = 8
    nodes_per_level = 20
    level_height = 3.0
    radius = 15.0
    # ---------------------

    for level in range(num_levels):
        for i in range(nodes_per_level):
            angle = (i / float(nodes_per_level)) * 2 * math.pi
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            y = level * level_height
            nodes.append({
                "id": f"node_{level}_{i}",
                "position": {"x": x, "y": y, "z": z}
            })

    # === 経路生成ロジックの変更箇所 START ===

    edges = []
    path_length = 20  # 経路の長さを設定

    # 1. 経路の最初のノードをランダムに選ぶ
    start_level = random.randint(0, num_levels - 1)
    start_node_index = random.randint(0, nodes_per_level - 1)
    previous_target_id = f"node_{start_level}_{start_node_index}"

    # 2. 指定した長さの連続した経路を生成
    for _ in range(path_length):
        # 現在の始点は、前の終点
        source_id = previous_target_id
        
        # 次の終点をランダムに選択
        next_target_level = random.randint(0, num_levels - 1)
        next_target_node_index = random.randint(0, nodes_per_level - 1)
        next_target_id = f"node_{next_target_level}_{next_target_node_index}"

        # 始点と終点が同じにならないようにする
        while source_id == next_target_id:
            next_target_level = random.randint(0, num_levels - 1)
            next_target_node_index = random.randint(0, nodes_per_level - 1)
            next_target_id = f"node_{next_target_level}_{next_target_node_index}"

        # 経路（edge）を作成してリストに追加
        edges.append({
            "source": source_id,
            "target": next_target_id
        })
        
        # 次のループのため、今回の終点を記憶しておく
        previous_target_id = next_target_id

    # === 経路生成ロジックの変更箇所 END ===
        
    return {"nodes": nodes, "edges": edges}


# Unityからの接続を処理するメイン部分
async def handler(websocket, path):
    print("✅ Unity client connected!")
    try:
        while True:
            graph_data = create_cylindrical_graph_data()
            await websocket.send(json.dumps(graph_data))
            await asyncio.sleep(3)  # 5秒ごとにデータを更新
    except websockets.exceptions.ConnectionClosed:
        print("🔌 Unity client disconnected.")


# サーバーを起動
async def main():
    print("🚀 Python WebSocket server started at ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())