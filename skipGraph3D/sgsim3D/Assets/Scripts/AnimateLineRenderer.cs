using UnityEngine;

public class AnimateLineRenderer : MonoBehaviour
{
    public float scrollSpeed = -1.0f; // テクスチャが流れる速さ
    private LineRenderer lineRenderer;

    void Start()
    {
        // このスクリプトがアタッチされているオブジェクトのLineRendererを取得
        lineRenderer = GetComponent<LineRenderer>();
    }

    void Update()
    {
        // 現在のテクスチャオフセットを取得
        Vector2 currentOffset = lineRenderer.material.mainTextureOffset;

        // X方向にテクスチャをスクロールさせる
        currentOffset.x += Time.deltaTime * scrollSpeed;

        // 新しいオフセットを設定
        lineRenderer.material.mainTextureOffset = currentOffset;
    }
}