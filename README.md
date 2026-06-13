# hermes-extensions

yqYo1's Hermes Agent plugins and skills collection.

## 概要

このリポジトリは、Hermes Agent用の自作プラグインとスキルをまとめて管理するためのものです。

## ディレクトリ構成

```
hermes-extensions/
├── plugins/                          # Hermes プラグイン
│   └── delegate-task-full-inheritance/   # delegate_task のツール限定を禁止するプラグイン
│       ├── plugin.yaml              # プラグインマニフェスト
│       ├── __init__.py              # エントリポイント（register(ctx)）
│       └── README.md                # プラグイン個別の説明
├── skills/                          # Hermes スキル（将来的に追加予定）
│   └── (skill-name)/
│       └── SKILL.md
├── LICENSE                          # MIT License
└── README.md                        # このファイル
```

## プラグイン一覧

### delegate-task-full-inheritance

`delegate_task` で `toolsets` パラメータを指定してツールを限定することを禁止するプラグイン。

**目的:**
- サブエージェントが親のツールセットを完全に継承することを強制する
- ツールの限定による意図しない機能制限を防ぐ

**動作:**
- `delegate_task` の呼び出し時に `toolsets` パラメータが存在する場合、ブロックしてエラーを返す
- ブロック理由は LLM にも通知され、再試行を促す

## インストール方法

### リポジトリのクローン

```bash
ghq get git@github.com:yqYo1/hermes-extensions.git
```

### プラグインのインストール

```bash
# シンボリックリンクでインストール（推奨）
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/delegate-task-full-inheritance ~/.hermes/plugins/

# 有効化
hermes plugins enable delegate-task-full-inheritance
```

シンボリックリンクを使用すると、リポジトリを `git pull` するだけでプラグインの更新が即座に反映されます。

### スキルのインストール

```bash
# シンボリックリンクでインストール
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/skills/<skill-name> ~/.hermes/skills/
```

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照してください。
