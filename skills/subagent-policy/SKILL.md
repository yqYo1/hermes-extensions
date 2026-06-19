---
name: subagent-policy
description: "サブエージェント（delegate_task）の利用方針、使い方、制約、ベストプラクティスを定義するスキル。SOUL.mdとsubagent-driven-developmentを中心に、サブエージェントの役割分担から実装パターンまでを網羅的に記述する。"
version: 1.0.0
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

`~/.hermes/config.yaml` の `delegation` セクションで設定する。

| 設定項目 | デフォルト値 | 説明 |
| -------- | ---------- | ---- |
| `max_concurrent_children` | 5 | 同時実行できる最大サブエージェント数 |
| `max_spawn_depth` | 4 | サブエージェントの最大ネスト深度 |
| `child_timeout_seconds` | 0（無制限） | サブエージェントあたりのタイムアウト（秒） |
| `max_iterations` | 50 | サブエージェントあたりの最大イテレーション数 |
| `orchestrator_enabled` | true | `role="orchestrator"` の有効化 |
| `subagent_auto_approve` | false | 危険コマンドの自動承認（false=自動否認） |

変更方法：

```bash
hermes config set delegation.max_concurrent_children 12
hermes config set delegation.max_spawn_depth 2
```

> **注意:** 変更は新しいセッションから有効。既存セッションには反映されない。

### 2.2. 並行数の計算例

```
Depth 1（PMが生成）: 最大12個
Depth 2（サブエージェントが生成）: 各々が最大12個 → 12 × 12 = 144個
Depth 3: 144 × 12 = 1,728個
Depth 4: 1,728 × 12 = 20,736個
```

| 構成 | Children | Depth | 理論最大 | 用途 |
| ---- | -------- | ----- | -------- | ---- |
| デフォルト | 5 | 4 | 780 | バランス型 |
| 重並列 | 12 | 2 | 156 | 多並列・浅いネスト |
| 深オーケストレーション | 5 | 4 | 780 | 複雑な多層委任 |
| 保守的 | 3 | 2 | 12 | リソース制限・単純タスク |

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

### 3.3. ブロックされるツール

リーフサブエージェント（`role="leaf"`）からは以下のツールが自動的に削除される：

| ブロックツール | 理由 |
| -------------- | ---- |
| `delegate_task` | 再帰的委任防止 |
| `clarify` | サブエージェントでのユーザー対話禁止 |
| `memory` | 共有メモリへの書き込み禁止 |
| `send_message` | クロスプラットフォーム副作用禁止 |
| `execute_code` | 子はステップバイステップで推論すべき |

オーケストレーター（`role="orchestrator"`）は `delegate_task` を保持できる（深度制限あり）。

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

### 4.2. タイムアウトとリソース

| 項目 | デフォルト | 備考 |
| ---- | ---------- | ---- |
| ハードタイムアウト | 600秒 | `child_timeout_seconds` で変更 |
| 0-APIコール診断 | 自動 | `~/.hermes/logs/subagent-timeout-*.log` に出力 |
| ハートビート | 30秒間隔 | 150秒アイドルまたは600秒同ツールで停止 |

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
    ),
    toolsets=["terminal", "file", "web", "skills"]
)
```

> **注意:** `context` はシステムプロンプトの中間に配置されるため、長いセッションでは「lost in the middle」で劣化する可能性がある。重要な規則は簡潔に、かつ冒頭に近い位置に記載する。

### 5.2. スキルへのアクセス

サブエージェントにスキルを認識させるには、以下のいずれかが必要：

1. `toolsets` パラメータを完全に省略（親のフルツールセットを継承）
2. `toolsets` 配列に `"skills"` を明示的に含める

**対処:** `toolsets`を省略するか、`"skills"`を含める。

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

**クリーンアップ手順:**

```bash
# すべてのローカルブランチを一覧（main/defaultを除く）
git branch | grep -v "main\|develop"

# すべてのリモートブランチを一覧
git branch -r

# リモート一時ブランチを削除
git push origin --delete <temp-branch-1> <temp-branch-2> ...

# ローカルワークツリーを削除（ブランチ削除前にワークツリーを削除）
git worktree remove <worktree-path>          # クリーンな場合
git worktree remove --force <worktree-path>  # ダーティな場合

# ローカルブランチを削除
git branch -D <temp-branch-1> <temp-branch-2> ...
```

---

## 6. トラブルシューティング

### 6.1. サブエージェントがスキルを認識しない

**症状:** サブエージェントに「`opencode`スキルを使用して」と指示しても、`skill_view`を呼ばず、スキルが存在しないと主張する。

**原因:** `toolsets`に`"skills"`が含まれていない。

**対処:** `toolsets`を省略するか、`"skills"`を含める。

### 6.2. Copilot ACP ルーティングエラー

**症状:**

```
[subagent-0] API call failed after 3 retries. Could not start Copilot ACP command 'claude'.
```

**原因:** プロバイダー解決が`command`フィールドを返し、子が`copilot-acp`に強制ルーティングされる。

**対処:** プロバイダーのランタイムエントリーが`command`フィールドを返さないようにする。`.env`にAPIキーが設定されていることを確認。

### 6.3. タイムアウト

**症状:** サブエージェントが600秒でタイムアウトする。

**原因:** `child_timeout_seconds`のデフォルトは0（無制限）だが、ドキュメントでは600秒と記載されている場合がある。実際のコードでは0が無制限を意味する。

**対処:** `~/.hermes/config.yaml`で`child_timeout_seconds`を確認・設定する。

```bash
hermes config set delegation.child_timeout_seconds 0  # 無制限
```

---

## 7. レビューとトリアージ

### 7.1. サブエージェントのレビュー結果の扱い

サブエージェントは深刻度を誤って分類する傾向がある。PMが再分類する必要がある。

| サブエージェントの判断 | 実際のカテゴリ | 対処 |
| ---------------------- | -------------- | ---- |
| P0（重大） | 仕様内部の矛盾 | 即座に修正 |
| P0（重大） | 仕様が実装を先行 | 「将来の作業」として文書化 |
| P1（高） | 実装をブロックする曖昧さ | grill-meで決定 |
| P2（改善） | 構造的改善 | 次の改訂でスケジュール |

### 7.2. トリアージ決定木

```
サブエージェントが発見を報告
├── 仕様内部の矛盾か？
│   ├── 同じセクションが自身と矛盾？ → P0、即座に修正
│   └── 異なるセクションが互いに矛盾？ → P0、即座に修正
├── 仕様と実装の間のギャップか？
│   ├── 仕様がgrill-meの決定と一致？ → 実装が更新を必要
│   ├── 実装がgrill-meの決定と一致？ → 仕様が更新を必要（P1）
│   └── どちらもgrill-meと一致しない？ → grill-meで決定（P1）
├── 「欠落した」機能/APIか？
│   ├── grill-meで明示的に決定？ → 仕様に含まれるべき（P1）
│   ├── grill-meで明示的に拒否？ → サブエージェントは間違い（無視）
│   └── 議論されたことがない？ → スコープ外の可能性（延期）
└── スタイル/一貫性の問題か？
    ├── 用語の不一致？ → 自律的に修正（P2）
    ├── 例のスタイルが異なる？ → 自律的に修正（P2）
    └── サブエージェントの個人的な好み？ → 無視
```

---

## 8. 関連スキル

| スキル | 役割 |
| ------ | ---- |
| `hermes-agent` | Hermes Agentの設定、拡張、使用方法 |
| `git-workflow` | ghq + worktreeモード、ブランチ管理、PR規約 |
| `specification-authoring` | 仕様書の作成、監査、レビュー |
| `opencode` | OpenCode CLIを使用したコードレビュー、実装 |

---

## 9. 参考情報

### 9.1. ソースコード参照

| ファイル | 行 | 内容 |
| -------- | ---- | ---- |
| `tools/delegate_tool.py` | 1229 | `skip_memory=True`（ハードコード） |
| `tools/delegate_tool.py` | 1228 | `skip_context_files=True`（ハードコード） |
| `tools/delegate_tool.py` | 564 | `_build_child_system_prompt()` 実装 |
| `tools/delegate_tool.py` | 1101 | `AIAgent(..., skip_memory=True, skip_context_files=True)` |
| `hermes_cli/config.py` | - | `delegation` セクションのデフォルト値 |

### 9.2. 設定確認コマンド

```bash
# 現在のdelegation設定を確認
hermes config show | grep -A 15 "delegation:"

# 直接config.yamlを確認
cat ~/.hermes/config.yaml | grep -A 20 "delegation:"
```

---

**最終更新:** 2026-06-20
**対象バージョン:** hermes-agent 2.0.0+
