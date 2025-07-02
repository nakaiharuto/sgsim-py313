using UnityEngine;

public class NodeAnimator : MonoBehaviour
{
    // Unityエディタのインスペクタで調整できる変数
    public float scaleAmount = 0.5f; // 拡大・縮小する量
    public float speed = 2.5f;       // アニメーションの速さ

    private Vector3 initialScale;    // 初期の大きさを保存する変数

    void Start()
    {
        // 実行開始時の、このオブジェクトの大きさを記憶しておく
        initialScale = transform.localScale;
    }

    void Update()
    {
        // 時間の経過と共に-1から1の間を滑らかに変化する値を作る
        float scaleFactor = Mathf.Sin(Time.time * speed) * scaleAmount;

        // 初期の大きさに、計算した変化量を加算して、新しい大きさに設定する
        transform.localScale = initialScale + new Vector3(scaleFactor, scaleFactor, scaleFactor);
    }
}