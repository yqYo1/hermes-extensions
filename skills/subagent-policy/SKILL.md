---
name: subagent-policy
description: "サブエージェント（delegate_task）の利用方針、使い方、制約、ベストプラクティスを定義するスキル。SOUL.mdとsubagent-driven-developmentを中心に、サブエージェントの役割分担から実装パターンまでを網羅的に記述する。"
version: 1.1.0
author: yaYoi
license: MIT
metadata:
  hermes:
    tags: [subagent, delegate_task, policy, best-practices, hermes-agent]
    related_skills: [hermes-agent, git-workflow, specification-authoring]
---

# サブエージェント運用方針

## 1. 基本原則

### 1.1. Delegate First, Execute Never

メインエージェント（PM）は計画・分解・委任判断・結果統合・ユーザー連絡のみを行う。

| 役割 | 担当者 | 責務 |
| ---- | ------ | ---- |
| **PM** | メインエージェント | タスク分析、分解、委任判断、結果統合、ユーザー連絡 |
| **Programmer** | OpenCode / コーディングサブエージェント | すべてのコード作業（実装、リファクタリング、レビュー、テスト） |
| **PL/Researcher** | サブエージェント（delegate_task） | 調査、分析、情報収集 |
| **Worker** | サブエージェント（delegate_task, leaf） | 単一ステップの機械的タスク、ファイル操作、コマンド実行 |

### 1.2. 委任対象と直接実行の境界

| 委任対象（必ずサブエージェントへ） | 直接実行可（メインエージェントが行う） |
| ----------------------------------- | ---------------------------------------- |
| すべてのコーディング | 分析、計画 |
| すべての調査・研究 | 統合、連絡 |
| すべての機械的実行 | 些細な調査（ツール1回で済むもの） |

> **迷ったら委任する。**

---

## 2. サブエージェントの設定

### 2.1. 並行性設定

| 設定項目 | 現在の値 | 説明 |
| -------- | -------- | ---- |
| `max_concurrent_children` | 12 | 同期バッチあたりの最大サブエージェント数 |
| `max_async_children` | 3 | バックグラウンド（background=true）サブエージェントの最大同時数。超過時はリジェクト（キューイングなし） |
| `max_spawn_depth` | 2 | 委任ツリーの深さ上限。1=フラット、2+=ネストされたオーケストレーション |
| `orchestrator_enabled` | true | `role="orchestrator"` の有効化 |
| `inherit_mcp_toolsets` | true | MCPツールセットを子に継承するか |

> 上記の「現在の値」は `~/.hermes/config.yaml` の現在の設定に基づく。タスク分割の判断材料として参照すること。

### 2.2. 並行数の計算例

現在の設定（`max_concurrent_children=12`, `max_spawn_depth=2`）での計算:

```
Depth 0: PM（メインエージェント）
Depth 1（PMが生成）: 最大12個のサブエージェント
Depth 2（各サブエージェントが生成、orchestratorのみ）: 各々が最大12個 → 12 × 12 = 144個
合計（理論最大）: 1 + 12 + 144 = 157個
```

---

## 3. サブエージェントの使い方

### 3.1. 基本的な呼び出し

```python
delegate_task(
    goal="調査タスクの説明",
    context="必要な背景情報や制約",
)
```

### 3.2. ツールセットの指定

| 指定方法 | 動作 | 推奨ケース |
| -------- | ---- | ---------- |
| `toolsets` 省略 | 親のフルツールセットを継承 | 通常はこれ（最も安全） |
| `toolsets=["terminal", "file", "web", "skills"]` | 指定したツールのみ（親と交差） | セキュリティ制限が必要な場合 |

> **重要:** `"skills"` を含めないとサブエージェントはスキルを認識できない。
>
> **注意（この環境特有）:** 同一リポジトリの `delegate-task-full-inheritance` プラグインが、明示的な `toolsets` パラメータをブロックする。サブエージェントは常に親のフルツールセットを継承するため、`toolsets` パラメータは省略して呼び出す必要がある。本ドキュメント中の `toolsets` を明示的に指定するコード例は、この環境ではすべてエラー（ブロック）となる。

### 3.3. ブロックされるツール

リーフサブエージェント（`role="leaf"`）からは以下のツールが自動的に削除される：

| ブロックツール | 理由 |
| -------------- | ---- |
| `delegate_task` | 再帰的委任防止 |
| `clarify` | サブエージェントでのユーザー対話禁止 |
| `memory` | 共有メモリへの書き込み禁止 |
| `send_message` | クロスプラットフォーム副作用禁止 |
| `execute_code` | 子はステップバイステップで推論すべき |

オーケストレーター（`role="orchestrator"`）は、上記のブロック対象ツールのうち `delegate_task` のみを例外として保持し、それ以外（`clarify` / `memory` / `send_message` / `execute_code`）はリーフと同様に削除される。なお、ファイル・ターミナル等の通常ツールはリーフと同様に利用可能。`max_spawn_depth` によりネスト深度が制限される。

### 3.4. オーケストレーターとリーフの使い分け

| 役割 | 用途 | ネスト |
| ---- | ---- | ------ |
| `leaf`（デフォルト） | 単一タスクの実行 | これ以上委任しない |
| `orchestrator` | 複数タスクの調整・並列実行 | さらに子を生成できる |

```python
# オーケストレーター例
delegate_task(
    goal="複数ファイルを並列で修正する",
    role="orchestrator",
    tasks=[
        {"goal": "ファイルAを修正"},
        {"goal": "ファイルBを修正"},
    ]
)
```

---

## 4. サブエージェントの制約

### 4.1. 継承されないもの

| 項目 | 親 | 子（サブエージェント） | 対処法 |
| ---- | ---- | ---------------------- | ------ |
| SOUL.md | ✅ 読み込まれる | ❌ 読み込まれない | `context` パラメータで重要な規則を渡す |
| メモリ | ✅ 有効 | ❌ `skip_memory=True` | `context` パラメータで情報を渡す |
| コンテキストファイル | ✅ 読み込まれる | ❌ `skip_context_files=True` | `context` パラメータで情報を渡す |
| プラグインフック | ✅ 発火する | ❌ 発火しない | フック内の処理は親で完結させる |
| フォールバックプロバイダー | ✅ 有効 | ❌ 継承されない | プロキシ側で設定 |

---

## 5. ベストプラクティス

### 5.1. context パラメータの活用

サブエージェントに重要な行動規則を渡すには `context` パラメータを使用する。

```python
delegate_task(
    goal="コードレビューを実施する",
    context=(
        "CRITICAL RULES (must follow):\n"
        "- Main agent's role is planning only; ALL execution delegated to subagents.\n"
        "- Subagent instructions MUST be written in English.\n"
        "- For coding tasks: read opencode skill first, then run opencode CLI inside delegate_task.\n"
        "- NEVER run opencode directly; always inside a subagent.\n"
        "- Before presenting changes: run CI checks AND opencode review.\n"
        "- Use ghq for cloning. Never commit to main.\n"
        "- nix-first: check flake.nix before raw commands.\n"
        "\n"
        "ORIGINAL TASK CONTEXT:\n"
        "[... actual task context here ...]"
    )
)
```

> **注意:** `context` はシステムプロンプトの中間に配置されるため、長いセッションでは「lost in the middle」で劣化する可能性がある。重要な規則は簡潔に、かつ冒頭に近い位置に記載する。

### 5.2. スキルへのアクセス

サブエージェントにスキルを認識させるには、以下のいずれかが必要：

1. `toolsets` パラメータを完全に省略（親のフルツールセットを継承）
2. `toolsets` 配列に `"skills"` を明示的に含める

```python
# 良い例: スキルアクセスを許可
delegate_task(
    goal="opencode skillを使ってレビューする",
    toolsets=["terminal", "file", "skills"]
)

# 悪い例: スキルアクセスが失われる
delegate_task(
    goal="opencode skillを使ってレビューする",
    toolsets=["terminal", "file"]  # skillsがない！
)
```

### 5.3. ワークツリーとブランチの管理

サブエージェントは多数の一時ブランチ・ワークツリーを作成する可能性がある。

**防止策:**

- 単一ブランチ命名規則を使用するよう指示
- 並列性が必要な場合のみ複数ブランチを作成

---

## 6. 関連スキル

| スキル | 役割 |
| ------ | ---- |
| `hermes-agent` | Hermes Agentの設定、拡張、使用方法 |
| `git-workflow` | ghq + worktreeモード、ブランチ管理、PR規約 |
| `specification-authoring` | 仕様書の作成、監査、レビュー |
| `opencode` | OpenCode CLIを使用したコードレビュー、実装 |
