using System;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;

public class UnityMainThreadDispatcher : MonoBehaviour
{
    private static readonly Queue<Action> _executionQueue = new Queue<Action>();
    private static UnityMainThreadDispatcher _instance = null;

    // シングルトンインスタンスを取得するための公開プロパティ
    public static UnityMainThreadDispatcher Instance
    {
        get
        {
            if (_instance == null)
            {
                // シーン内からインスタンスを探す
                _instance = FindObjectOfType<UnityMainThreadDispatcher>();
                if (_instance == null)
                {
                    // 見つからなければエラーを出す
                    UnityEngine.Debug.LogError("UnityMainThreadDispatcher instance not found in the scene.");
                }
            }
            return _instance;
        }
    }

    // Unityのライフサイクルで、オブジェクトが有効になった時に呼ばれる
    private void Awake()
    {
        // まだインスタンスが存在しない場合
        if (_instance == null)
        {
            // このオブジェクトを唯一のインスタンスとして設定
            _instance = this;
            // シーンを切り替えてもこのオブジェクトが破壊されないようにする
            DontDestroyOnLoad(this.gameObject);
        }
        // 既に別のインスタンスが存在する場合
        else if (_instance != this)
        {
            // このオブジェクトは不要なので破棄する
            Destroy(gameObject);
        }
    }

    // メインスレッドで実行したい処理をキューに追加する
    public void Enqueue(Action action)
    {
        lock (_executionQueue)
        {
            _executionQueue.Enqueue(action);
        }
    }

    // 毎フレーム呼ばれ、キューにたまった処理を実行する
    private void Update()
    {
        lock (_executionQueue)
        {
            while (_executionQueue.Count > 0)
            {
                _executionQueue.Dequeue().Invoke();
            }
        }
    }
}