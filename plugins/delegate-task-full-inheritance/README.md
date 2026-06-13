# delegate-task-full-inheritance

`delegate_task` で `toolsets` パラメータを指定してツールを限定することを禁止する Hermes Agent プラグイン。

## 目的

サブエージェントが親のツールセットを完全に継承することを強制します。これにより、ツールの限定による意図しない機能制限を防ぎます。

## 動作

- `delegate_task` の呼び出し時に `toolsets` パラメータが存在する場合、ブロックしてエラーを返します
- 単一タスクモード（`goal` + `toolsets`）とバッチモード（`tasks` 配列内の各タスク）の両方を検出します
- ブロック理由はツールエラーとして返され、**LLM にも通知されます**
- LLM はエラーメッセージを確認し、`toolsets` パラメータを省略して再試行できます

## インストール

```bash
# このプラグインディレクトリを Hermes の plugins ディレクトリにコピー
cp -r /path/to/hermes-extensions/plugins/delegate-task-full-inheritance ~/.hermes/plugins/

# 有効化
hermes plugins enable delegate-task-full-inheritance
```

## 設定

`~/.hermes/config.yaml` で有効化状態を確認できます：

```yaml
plugins:
  enabled:
    - delegate-task-full-inheritance
```

新しいセション（`/reset`）でプラグインが読み込まれます。

## ブロックメッセージ例

### 単一タスクモード

```
delegate_task with explicit 'toolsets' parameter is blocked. Subagents must inherit the parent's full toolset. Remove the 'toolsets' parameter to allow full inheritance.
```

### バッチモード

```
delegate_task batch mode: task 0 has explicit 'toolsets' parameter. Subagents must inherit the parent's full toolset. Remove 'toolsets' from task 0 to allow full inheritance.
```

## ライセンス

MIT License
