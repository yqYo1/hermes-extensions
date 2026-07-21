# Loop Detector Plugin

Hermes Agent のセッション中に以下の 2 種類のループを検知し、ブロックと通知によって被害を抑止します。

1. **ツール呼び出しループ（Tool Loop）**: 同じツールを同じ引数で繰り返し呼び出す振る舞いを検知・ブロック
2. **応答ループ（Response Loop）**: LLM が出力テキスト（`assistant_message.content`、全 API 呼び出しの出力でターン内の中間出力を含む）で同じ内容・同じ推論パターンを繰り返し出力する振る舞いを検知・通知（thinking／推論トレースではなく通常出力が対象）

## インストール

```bash
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/loop-detector ~/.hermes/plugins/
hermes plugins enable loop-detector
```

## 動作

| フック / middleware | タイミング | 動作 |
| ------ | ---------- | ---- |
| `pre_tool_call` | ツール呼び出し前 | ツールループを検知し `{"action": "block"}` でブロック |
| `post_api_request` | LLM API 呼び出しごと | `assistant_message.content` を記録し応答ループを検知（ターン内の中間出力を含む・割り込み時も発火） |
| `llm_request`（middleware） | LLM API 呼び出し直前 | 応答ループ検出時、ターン内の次の API リクエストに回復通知を即時注入 |
| `pre_llm_call` | ターン開始時 | ターン内で注入されなかった回復通知を次ターンに注入（補助） |
| `on_session_reset` | セッションリセット | セッション状態を削除 |

## ループ検知アルゴリズム

### ツールループ（厳密一致ベース）

- 同一 `(tool_name, 正規化引数)` の連続 3 回（`consecutive_threshold`）
- 直近 10 件中に同一呼び出し 4 回以上（`window_size` / `window_threshold`）
- A→B→A→B… の交互パターン（周期 2/3、6 件以上連続）

### 応答ループ（類似度ベース）

- 直近の `assistant_message.content`（全 API 呼び出しの出力テキスト、ターン内の中間出力を含む）を正規化し、隣接ペアを `difflib` で比較
- **現在も継続中のループのみ検出**（直近が類似ペアで終わる trailing run が 3 以上）。
  自力脱出済みのループは検出しない
- 類似度 0.95 以上のペアが直近から 3 組連続で検出

## LLM 確認

検出時に意図的な繰り返し（ポーリング・CI 待ち等）を除外するため、構造化 LLM 確認を行います。

- `is_loop: false`（意図的）と判定されたパターンはセッション内で許可リスト登録
- 確認失敗時は既定で fail-closed（ブロック）。`confirmation.on_error: allow` で変更可能
- `confirmation.enabled: false` で確認を無効化（検出時即ブロック）

## 回復通知

ループがブロック・検出された場合、次ターンの LLM 呼び出し時にユーザーメッセージへ
エフェメラルな回復通知を注入します（プロンプトキャッシュ維持・永続化なし・CLI/ゲートウェイ両対応）。

## 設定

`~/.hermes/config.yaml` に以下を追加（`config.yaml.example` 参照）：

```yaml
plugins:
  loop_detector:
    enabled: true
    tool_loop:
      enabled: true
      consecutive_threshold: 3
      window_size: 10
      window_threshold: 4
      alternating_enabled: true
      alternating_min_length: 6
    response_loop:
      enabled: true
      similarity_threshold: 0.95
      window_size: 10
      min_repetitions: 3
    confirmation:
      enabled: true
      on_error: block
      timeout: 30
    response:
      max_blocks_per_session: 5
      recovery_notice: ""
```

## 制限

- 巻き戻しは行いません（インメモリ履歴をプラグインから操作する公式手段が存在しないため）。
  ブロックと通知による抑止に留まります
- 応答ループはブロックできません（ブロック可能なゲートは `pre_tool_call` のみ）
- 検出履歴・許可リストはオンメモリのため、プロセス再起動で失われます

詳細な設計仕様は [SPEC.md](SPEC.md) を参照してください。
