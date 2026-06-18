---
name: loop-detector
version: 1.0.0
description: "Detects LLM thinking loops and tool-call loops, rolls back to pre-loop state, and retries with a recovery prompt."
author: yqYo1
license: MIT
hooks:
  - pre_tool_call
  - post_llm_call
  - on_session_end
  - on_session_reset
---

# Loop Detector Plugin

## 1. 目的

Hermes Agent のセッション中に以下の 2 種類のループを検知し、検知した場合はループ前の状態に巻き戻して再試行する。

1. **思考ループ（Thinking Loop）**: 同じ内容や同じ推論パターンを繰り返し出力する LLM の振る舞い
2. **ツール呼び出しループ（Tool Loop）**: 同じツールを同じ引数で繰り返し呼び出す振る舞い

## 2. 設計方針

- **検知は軽量に**: 完全一致ではなく類似度ベースで検知。編集距離やハッシュ比較を使う
- **巻き戻しは安全に**: セッションDBのメッセージ履歴を直接操作し、ループ開始点まで削除
- **再試行は賢く**: 巻き戻し後、モデルに「前回の試行でループが発生した」ことを通知する回復プロンプトを注入
- **設定可能**: 検知閾値、履歴比較ウィンドウ、最大再試行回数を config.yaml で調整可能

## 3. ループ検知アルゴリズム

### 3.1 思考ループ検知

```
入力: 直近 N ターンの assistant メッセージ群
出力: ループ検知フラグ + ループ開始インデックス

1. 各 assistant メッセージの「思考部分」を抽出（ reasoning / think タグ内）
2. 直近 3 ターンの思考テキストをペアワイズ比較
3. 類似度 > 閾値（デフォルト 0.85）のペアが 2 組以上連続で存在 → ループ判定
4. 類似度計算: 正規化したテキストの編集距離比率
```

### 3.2 ツール呼び出しループ検知

```
入力: 直近 M 回の tool_calls 群
出力: ループ検知フラグ + ループ開始インデックス

1. 各 tool_call を (tool_name, normalized_args) のタプルに変換
2. 直近 3 回の tool_call セットを比較
3. 完全一致または引数の 90% 以上が一致 → ループ判定
4. 特殊ケース: 連続する browser_navigate → browser_click → browser_navigate → browser_click などの交互パターンも検知
```

## 4. 巻き戻し機構

### 4.1 巻き戻し対象

- セッションDB (`~/.hermes/state.db`) 内のメッセージテーブル
- ループ開始点（検知された最初の繰り返しターン）より後のメッセージを全て削除

### 4.2 巻き戻し手順

```
1. SessionDB.get_messages(session_id) で全メッセージを取得
2. ループ開始インデックスを特定
3. そのインデックス以降のメッセージを DB から削除
4. メモリ上の conversation_history も同様にトリム
```

### 4.3 回復プロンプト注入

巻き戻し後、次の LLM 呼び出し前に以下のコンテキストを注入:

```
[system notification]
前回の試行でループが検知されました。以下に注意してください:
- 同じ推論や同じツール呼び出しを繰り返さないでください
- 異なるアプローチや別のツールを検討してください
- すでに試行済みの内容は省略し、次のステップに進んでください
```

## 5. 設定項目

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

## 6. 実装ファイル構成

```
~/.hermes/plugins/loop-detector/
├── plugin.yaml          # マニフェスト
├── __init__.py          # register() とメインライン
├── detector.py          # ループ検知アルゴリズム
├── rollback.py          # 巻き戻し・DB操作
└── config.py            # 設定読み込み
```

## 7. フック使用計画

| フック | 用途 |
|--------|------|
| `post_llm_call` | assistant メッセージを受け取り、思考ループ検知 |
| `pre_tool_call` | ツール呼び出し前にツールループ検知・ブロック |
| `on_session_end` | セッション状態のクリーンアップ |
| `on_session_reset` | リセット時の状態初期化 |

## 8. 制限事項・注意点

- プラグインは `pre_tool_call` でブロック可能だが、既存のメッセージを削除する権限はない
- SessionDB への直接アクセスは可能だが、メモリ上の `conversation_history` はエージェント本体が管理
- 巻き戻し後の回復プロンプトは `pre_llm_call` または `inject_message()` で注入
- 再試行回数の上限を設け、無限ループを防ぐ
