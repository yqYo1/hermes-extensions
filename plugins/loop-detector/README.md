# Loop Detector Plugin

Hermes Agent のセッション中に以下の 2 種類のループを検知し、検知した場合はループ前の状態に巻き戻して再試行します。

## 機能

1. **思考ループ（Thinking Loop）**: 同じ内容や同じ推論パターンを繰り返し出力する LLM の振る舞いを検知
2. **ツール呼び出しループ（Tool Loop）**: 同じツールを同じ引数で繰り返し呼び出す振る舞いを検知・ブロック

## インストール

```bash
# プラグインを有効化
hermes plugins enable loop-detector
```

## 設定

`~/.hermes/config.yaml` に以下を追加：

```yaml
plugins:
  loop_detector:
    enabled: true
    thinking_loop:
      enabled: true
      similarity_threshold: 0.85      # 類似度閾値 (0.0-1.0)
      window_size: 5                  # 比較対象の直近ターン数
      min_repetitions: 2              # ループ判定に必要な連続繰り返し数
    tool_loop:
      enabled: true
      max_identical_calls: 2          # 同じツール呼び出しの最大許容回数
      window_size: 6                  # 比較対象の直近ツール呼び出し数
    rollback:
      max_retries: 3                  # 1セッションあたりの最大再試行回数
      recovery_prompt: "..."          # 回復プロンプト（省略可）
```

## 動作

| フック | タイミング | 動作 |
| --------- | ----------- | ------- |
| `post_llm_call` | LLM応答後 | assistantメッセージを記録し、思考ループを検知 |
| `pre_tool_call` | ツール呼び出し前 | ツールループを検知し、ブロック |
| `on_session_end` | セッション終了 | 状態をクリーンアップ |
| `on_session_reset` | セッションリセット | 状態を初期化 |

## ループ検知アルゴリズム

### 思考ループ

- 直近 N ターンの assistant メッセージを比較
- 編集距離ベースの類似度で判定（デフォルト閾値 0.85）
- 連続する類似ペアが閾値以上 → ループ判定

### ツールループ

- 直近 M 回のツール呼び出しを比較
- 同じ (tool_name, args) の繰り返しを検知
- 交互パターン（A→B→A→B）も検知

## 巻き戻し

ループ検知時：

1. セッションDBからループ開始点以降のメッセージを削除
2. 回復プロンプトを会話に注入
3. モデルに異なるアプローチを取るよう通知

## 制限

- プラグインは `pre_tool_call` でツールをブロック可能
- メッセージ削除は SessionDB/SQLite を直接操作
- 再試行回数上限で無限ループを防止
