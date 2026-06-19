---
name: hermes-plugin-development
description: "Develop, debug, and deploy Hermes Agent plugins — directory structure, hooks, SessionDB, inject_message, and state management."
version: 1.0.0
author: yqYo1
license: MIT
metadata:
  hermes:
    tags: [hermes, plugin, development, hooks, lifecycle]
    related_skills: [hermes-agent]
---

# Hermes Plugin Development

Develop custom plugins for Hermes Agent. Covers directory structure, manifest format, lifecycle hooks, SessionDB access, and conversation state management.

## Directory Structure

Plugins are discovered from 4 sources (priority order):

| Source | Path | Notes |
|--------|------|-------|
| Bundled | `<repo>/plugins/<name>/` | Shipped with Hermes |
| User | `~/.hermes/plugins/<name>/` | User-installed |
| Project | `./.hermes/plugins/<name>/` | `HERMES_ENABLE_PROJECT_PLUGINS=1` |
| Pip | `setup.py` entry points | `hermes_agent.plugins` group |

**Required files per plugin:**

```
~/.hermes/plugins/<name>/
├── plugin.yaml          # Manifest
├── __init__.py          # register(ctx) function
└── ...                  # Supporting modules
```

## Manifest (plugin.yaml)

```yaml
name: my-plugin
version: 1.0.0
description: "What this plugin does"
author: "Name"
license: MIT
hooks:
  - pre_tool_call
  - post_llm_call
  - on_session_end
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Plugin identifier |
| `version` | No | Semver string |
| `description` | No | Human-readable description |
| `author` | No | Author name |
| `license` | No | License string |
| `hooks` | No | List of hooks this plugin registers |
| `requires_env` | No | Required environment variables |
| `provides_tools` | No | Tools provided by this plugin |
| `kind` | No | `standalone` (default), `backend`, `exclusive`, `platform`, `model-provider` |

## register(ctx) Function

Every plugin must export `register(ctx)` in `__init__.py`:

```python
def register(ctx):
    ctx.register_hook("pre_tool_call", my_handler)
    ctx.register_hook("post_llm_call", my_observer)
    ctx.register_command("my-cmd", handler=cmd_handler, description="...")
```

**PluginContext methods:**

| Method | Purpose |
|--------|---------|
| `register_hook(name, callback)` | Register lifecycle hook |
| `register_tool(name, toolset, schema, handler)` | Register new tool |
| `register_command(name, handler, description, args_hint)` | Register slash command |
| `inject_message(content, role)` | Inject message into conversation |
| `dispatch_tool(tool_name, args)` | Dispatch tool from plugin |
| `llm` | Access PluginLlm for LLM calls |

## Hooks Reference

| Hook | Trigger | Timing | Can Block? | Key Kwargs |
|------|---------|--------|------------|------------|
| `pre_tool_call` | Before tool executes | Per tool call | **Yes** | `tool_name`, `args`, `task_id`, `session_id` |
| `post_tool_call` | After tool returns | Per tool call | No | `tool_name`, `args`, `result`, `session_id` |
| `pre_api_request` | Before LLM API call | **Per API call** (inside tool loop) | No | `messages`, `model`, `session_id` |
| `post_api_request` | After LLM API call | **Per API call** (inside tool loop) | No | `response`, `model`, `session_id` |
| `pre_llm_call` | Before LLM call (prologue) | **Once per user turn** (before tool loop) | No (injects context) | `user_message`, `conversation_history`, `session_id` |
| `post_llm_call` | After LLM response (epilogue) | **Once per user turn** (after tool loop) | No | `assistant_message`, `response`, `session_id` |
| `on_session_start` | New session | Once per session | No | `session_id`, `model`, `platform` |
| `on_session_end` | Session ends | Once per session | No | `session_id`, `task_id`, `completed`, `interrupted` |
| `on_session_reset` | `/reset` executed | Per reset | No | `session_id` |
| `on_session_finalize` | Full teardown | Once per session | No | `session_id` |

**Timing detail:** `pre_llm_call` / `post_llm_call` fire ONCE per user turn, in
the prologue/epilogue of `run_conversation()` (conversation_loop.py). They are
**not** called inside the tool-calling while loop. In contrast,
`pre_api_request` / `post_api_request` fire on **every API call iteration**
inside the loop. If you need per-request tracing or per-iteration data, use
`pre_api_request` — not `pre_llm_call`. The context from `pre_llm_call` is
collected once and reused across all loop iterations. This is an intentional
design to avoid redundant hook calls.

**Blocking syntax (pre_tool_call only):**

```python
return {"action": "block", "message": "Reason for blocking"}
```

## pre_llm_call Context Injection (Detailed)

`pre_llm_call` is the only hook whose return value affects the conversation.
When a callback returns `{"context": "..."}`, the text is **appended** to the
user message at API-call time — it is NOT prepended, NOT injected into the
system prompt, and NOT persisted to the session DB.

### How it works (3-step)

1. **Hook collection** (`turn_context.py:318-343`): All registered
   `pre_llm_call` callbacks fire. Their return values (`{"context": "..."}` or
   plain strings) are collected and joined with `"\n\n"` into a single
   `plugin_user_context` string. Order follows plugin discovery order.

2. **TurnContext storage** (`turn_context.py:58-59`): The merged string is
   stored in `TurnContext.plugin_user_context` — a dataclass field consumed
   by the conversation loop.

3. **API-call injection** (`conversation_loop.py:712-732`): Before each LLM
   API call, the current turn's user message content is augmented:

   ```python
   api_msg["content"] = _base + "\n\n" + "\n\n".join(_injections)
   ```

   The original `messages` list is never mutated — only the API-copy gets
   the injection. Changes are **ephemeral** (not persisted to session DB,
   not visible in transcripts).

### Kwargs received

```python
kwargs = {
    "session_id": str, "task_id": str, "turn_id": str,
    "user_message": str, "conversation_history": list,
    "is_first_turn": bool, "model": str, "platform": str,
    "sender_id": str,
}
```

### Return-value formats

```python
# Dict format (recommended — explicit key)
return {"context": "Additional text to append"}

# Plain string (also works)
return "Additional text to append"
```

### Comparison with other injection mechanisms

| Mechanism | Scope | Persisted? | Use Case |
|-----------|-------|------------|----------|
| `pre_llm_call` `{"context"}` | All platforms | No (ephemeral) | RAG, guardrails, suffix, memory prefetch |
| `ctx.inject_message()` | All platforms | Yes (appears next turn) | Recovery prompts, timed injections |
| `pre_gateway_dispatch` `"rewrite"` | Gateway only | Yes | Content filtering, message transformation |

See `references/pre-llm-call-context-injection.md` for a complete source-level
walkthrough, example suffix-injection plugin code, and pitfall table.

## Session State Management

Plugin module-level globals survive `/reset`. Use `session_id` keys for isolation:

```python
import threading

_lock = threading.Lock()
_session_state: Dict[str, Dict] = {}

def _get_state(session_id: str) -> Dict:
    with _lock:
        return _session_state.setdefault(session_id, {"count": 0})

def _on_session_end(session_id: str = "", **kwargs):
    with _lock:
        _session_state.pop(session_id, None)
```

**Always clean up on `on_session_end` or `on_session_reset`.**

## Accessing Conversation History

Plugins do NOT receive `conversation_history` directly in most hooks. Use SessionDB:

```python
from hermes_state import SessionDB

db = SessionDB()
messages = db.get_messages(session_id)  # List[Dict] with role, content, etc.
```

**Direct SQLite fallback** (if SessionDB API changes):

```python
import sqlite3
from hermes_cli.config import get_hermes_home

db_path = os.path.join(get_hermes_home(), "state.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
messages = [dict(row) for row in cursor.fetchall()]
conn.close()
```

## Injecting Recovery Messages

Use `ctx.inject_message()` to add context mid-conversation:

```python
def register(ctx):
    def on_loop_detected(session_id, **kwargs):
        ctx.inject_message("[recovery] Try a different approach.", role="user")
    # ...
```

**Note:** `inject_message()` adds to the interrupt queue. It will appear as a user message in the next turn.

## Configuration

Read plugin config from `config.yaml`:

```python
from hermes_cli.config import get_config

def _cfg() -> Dict:
    return get_config().get("plugins", {}).get("my_plugin", {})

def _enabled() -> bool:
    return _cfg().get("enabled", True)
```

**Config location:** `~/.hermes/config.yaml` under `plugins.<name>`.

## Enabling/Disabling Plugins

```bash
hermes plugins list              # Show all plugins
hermes plugins enable <name>     # Enable plugin
hermes plugins disable <name>    # Disable plugin
```

**Activation:** Takes effect on next session (`/reset` or new `hermes` invocation).

## Testing Plugins

Test detection logic without running Hermes:

```python
# Test from plugin directory
import sys
sys.path.insert(0, '/path/to/hermes-agent')

from my_plugin.detector import detect_loop
detect_loop([...])  # Test with sample data
```

## Repository Management & Workflow

### Where to Store Plugin Source

**Never develop plugins directly in `~/.hermes/plugins/`.** The `~/.hermes/plugins/` directory is for **activation symlinks only**, not for source development.

**Correct workflow:**

1. **Develop** in the `hermes-extensions` repository (or your equivalent plugin collection repo):

   ```
   ~/ghq/github.com/yqYo1/hermes-extensions/plugins/<plugin-name>/
   ├── plugin.yaml
   ├── __init__.py
   └── ...
   ```

2. **Activate** via symlink to `~/.hermes/plugins/`:

   ```bash
   ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/<plugin-name> \
         ~/.hermes/plugins/<plugin-name>
   ```

3. **Enable** the plugin:

   ```bash
   hermes plugins enable <plugin-name>
   ```

### Worktree-Based Development

Follow the `git-workflow` skill (ghq + worktree mode) for all plugin development:

```bash
cd ~/ghq/github.com/yqYo1/hermes-extensions

# Create worktree (NEVER work in root directory)
git worktree add .worktree/add-<plugin-name>-plugin origin/main
cd .worktree/add-<plugin-name>-plugin
git checkout -b add-<plugin-name>-plugin

# Develop plugin in plugins/<plugin-name>/
# ... edit files ...

# Format and lint
nix run nixpkgs#ruff -- format plugins/<plugin-name>/
nix run nixpkgs#ruff -- check plugins/<plugin-name>/

# Commit and push from worktree
git add -A && git commit -m "feat: add <plugin-name> plugin" && git push
```

**Pitfall (2026-06-18 session):** Agent committed plugin files directly to `main` branch in root directory. User corrected: "なぜプラグインフォルダに直接置いてる?" → "hermes-extensionで管理して下さい。"

### Templates

- `templates/loop-detector-plugin.py` — Complete loop-detection plugin with thinking-loop and tool-loop detection, rollback, and recovery prompt injection. Copy and modify for your own plugin.

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Module globals not reset by `/reset` | Key state by `session_id`, clean up on `on_session_end` |
| `inject_message()` not appearing immediately | It goes to interrupt queue; appears next turn |
| SessionDB schema changes | Use `sqlite3` fallback with table auto-discovery |
| Plugin not loading | Check `plugin.yaml` syntax, `register()` export, `hooks` list |
| Hook not firing | Plugin must be enabled; hooks take effect on next session |
| Thread safety | Subagent threads can fire hooks concurrently; use locks |

## References

- `references/plugin-hooks.md` — Full hook kwargs and return semantics (bundled hermes-agent skill)
- `references/plugin-variable-lifetime.md` — State management deep dive (bundled hermes-agent skill)
- `references/plugin-development.md` — Advanced plugin patterns (bundled hermes-agent skill)
- `references/pre-llm-call-context-injection.md` — Source-level mechanics of `pre_llm_call` context injection, comparison with other injection methods, and a complete suffix-injection plugin example
