using UnityEngine;
using NativeWebSocket;
using System.Collections.Generic;
using System.Net.WebSockets;

// JSONデータに対応するC#クラス
[System.Serializable] public class Vector3Data { public float x, y, z; }
[System.Serializable] public class NodeData { public string id; public Vector3Data position; }
[System.Serializable] public class EdgeData { public string source; public string target; }
[System.Serializable] public class GraphData { public List<NodeData> nodes; public List<EdgeData> edges; }

public class GraphManager : MonoBehaviour
{
    NativeWebSocket.WebSocket websocket;

    // 事前にUnityエディタで作成しておくPrefab
    public GameObject nodePrefab; // ノード用のPrefab（例: Sphere）
    public LineRenderer edgePrefab; // 経路用のPrefab

    // 生成したオブジェクトを管理するための変数
    private Dictionary<string, GameObject> spawnedNodes = new Dictionary<string, GameObject>();
    private List<GameObject> spawnedEdges = new List<GameObject>();

    async void Start()
    {
        websocket = new NativeWebSocket.WebSocket("ws://localhost:8765");

        websocket.OnOpen += () => Debug.Log("✅ Connection open!");
        websocket.OnError += (e) => Debug.LogError("Error: " + e);
        websocket.OnClose += (e) => Debug.Log("🔌 Connection closed!");

        websocket.OnMessage += (bytes) =>
        {
            var message = System.Text.Encoding.UTF8.GetString(bytes);
            GraphData receivedData = JsonUtility.FromJson<GraphData>(message);
            UnityMainThreadDispatcher.Instance.Enqueue(() => UpdateGraphVisuals(receivedData));
        };

        await websocket.Connect();
    }

    void Update()
    {
        if (websocket != null) { websocket.DispatchMessageQueue(); }
    }

    // グラフの見た目を更新する関数
    void UpdateGraphVisuals(GraphData data)
    {
        // 既存のオブジェクトをクリア
        foreach (var pair in spawnedNodes) { Destroy(pair.Value); }
        foreach (var edge in spawnedEdges) { Destroy(edge); }
        spawnedNodes.Clear();
        spawnedEdges.Clear();

        // ノードを生成
        foreach (var node in data.nodes)
        {
            Vector3 pos = new Vector3(node.position.x, node.position.y, node.position.z);
            GameObject nodeObject = Instantiate(nodePrefab, pos, Quaternion.identity, this.transform);
            nodeObject.name = node.id;
            spawnedNodes.Add(node.id, nodeObject);
        }

        // 経路を生成
        foreach (var edge in data.edges)
        {
            if (spawnedNodes.TryGetValue(edge.source, out GameObject sourceNode) && spawnedNodes.TryGetValue(edge.target, out GameObject targetNode))
            {
                LineRenderer line = Instantiate(edgePrefab, this.transform);
                line.SetPosition(0, sourceNode.transform.position);
                line.SetPosition(1, targetNode.transform.position);
                spawnedEdges.Add(line.gameObject);
            }
        }
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null) { await websocket.Close(); }
    }
}