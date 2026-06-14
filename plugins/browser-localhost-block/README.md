# browser-localhost-block

ブラウザツールが localhost / 127.0.0.1 にアクセスするのをブロックし、代わりに tailscale IP を使用するように促す Hermes Agent プラグイン。

## 目的

この環境では、ブラウザバックエンドは Hermes が動作しているインスタンスとは別のインスタンスで動作しています。そのため、ブラウザツールから localhost にアクセスすると、ブラウザバックエンド自身の localhost に接続しようとするため、Hermes インスタンス上のサービスにはアクセスできません。

このプラグインは、localhost/127.0.0.1 へのアクセスをブロックし、tailscale IP (100.64.x.x) を使用するように指示します。

## 動作

- `browser_navigate` などのブラウザツールで localhost/127.0.0.1 URL を検出した場合にブロック
- ブロック時に動的に tailscale IP を取得（`tailscale ip` コマンドなど）
- tailscale IP が取得できた場合: その IP を提示
- 取得できなかった場合: tailscale IP の取得方法を提示

## ブロックメッセージ例

### tailscale IP 取得成功時

```
Browser tool blocked: attempted to access localhost (http://localhost:8080).
Reason: The browser backend runs on a separate instance from Hermes,
so localhost/127.0.0.1 would target the browser backend's own localhost,
not the Hermes instance.
Use the tailscale IP instead: http://100.64.0.8/
```

### tailscale IP 取得失敗時

```
Browser tool blocked: attempted to access localhost (http://localhost:8080).
Reason: The browser backend runs on a separate instance from Hermes,
so localhost/127.0.0.1 would target the browser backend's own localhost,
not the Hermes instance.
Please bind your service to the tailscale interface and use the tailscale
IP (100.64.x.x) for access. Run 'tailscale ip' to find your IP.
```

## インストール

```bash
# シンボリックリンクでインストール（推奨）
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/browser-localhost-block ~/.hermes/plugins/

# 有効化
hermes plugins enable browser-localhost-block
```

## ライセンス

MIT License
