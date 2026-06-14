# browser-localhost-block

Hermes Agent plugin that blocks browser tools from accessing localhost/127.0.0.1 and suggests using the tailscale IP instead.

## Purpose

In this environment, the browser backend runs on a separate instance from Hermes. Therefore, accessing localhost from browser tools would connect to the browser backend's own localhost, not the Hermes instance's services.

This plugin blocks localhost/127.0.0.1 access and instructs using the tailscale IP (100.64.x.x) instead.

## Behavior

- Blocks when localhost/127.0.0.1 URLs are detected in browser tool calls
- Dynamically retrieves tailscale IP at block time (`tailscale ip` command, etc.)
- If tailscale IP is found: presents that IP
- If retrieval fails: presents instructions on how to find the tailscale IP

## Block Message Examples

### When tailscale IP is retrieved

```
Browser tool blocked: attempted to access localhost (http://localhost:8080).
Reason: The browser backend runs on a separate instance from Hermes,
so localhost/127.0.0.1 would target the browser backend's own localhost,
not the Hermes instance.
Use the tailscale IP instead: http://100.64.0.8/
```

### When tailscale IP retrieval fails

```
Browser tool blocked: attempted to access localhost (http://localhost:8080).
Reason: The browser backend runs on a separate instance from Hermes,
so localhost/127.0.0.1 would target the browser backend's own localhost,
not the Hermes instance.
Please bind your service to the tailscale interface and use the tailscale
IP (100.64.x.x) for access. Run 'tailscale ip' to find your IP.
```

## Installation

```bash
# Symlink installation (recommended)
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/browser-localhost-block ~/.hermes/plugins/

# Enable
hermes plugins enable browser-localhost-block
```

## License

MIT License
