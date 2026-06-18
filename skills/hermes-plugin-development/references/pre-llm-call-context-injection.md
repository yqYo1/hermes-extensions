# `pre_llm_call` Context Injection — Source-Level Mechanics

Source-of-truth trace through the Hermes Agent codebase for how plugin
context reaches the LLM API call.

## Flow Summary

```text
User sends message
       │
       ▼
turn_context.py:build_turn_context()
  └─ invoke_hook("pre_llm_call", ...)       ← plugin returns {"context": "..."}
  └─ collects all non-None results
  └─ joins with "\n\n" → plugin_user_context
       │
       ▼
TurnContext(user_message=..., plugin_user_context=str)
       │
       ▼
conversation_loop.py (per loop iteration)
  └─ api_msg["content"] = _base + "\n\n" + "\n\n".join(_injections)
       │
       ▼
LLM API call ← ephemeral only, never persisted
```

## Timing Analysis: Once Per User Turn (Critical Distinction)

This is the most common source of confusion about `pre_llm_call`. The hook fires
**exactly once per user turn**, in the prologue of `run_conversation()`. It does
**NOT** fire on every tool-loop iteration.

### Call Chain

```
run_conversation(user_message, ...)           ← conversation_loop.py:469
  │
  ├── build_turn_context(agent, user_message, ...)  ← line 508
  │     │
  │     ├── ... reset counters, build messages ...
  │     │
  │     └── invoke_hook("pre_llm_call", ...)        ← turn_context.py:322
  │           │                                        ════════════════
  │           └── plugin callback(s) fire ONCE          FIRES HERE
  │                                                    ════════════════
  │
  ├── _ctx = TurnContext(plugin_user_context=...)  ← turn_context.py:378
  │
  │  ══════════════════════════════════════════════════════════
  │  ▼ Tool-calling loop — pre_llm_call does NOT fire here
  │  ══════════════════════════════════════════════════════════
  │
  ├── while (api_call_count < max_iterations):     ← line 563
  │     │
  │     ├── iteration 1: API call ← plugin_user_context REUSED
  │     │     (pre_api_request / post_api_request fire here)
  │     │
  │     ├── iteration 2: (tool result → another API call)
  │     │     (pre_api_request / post_api_request fire here)
  │     │
  │     └── iteration N: ...
  │           (pre_api_request / post_api_request fire here)
  │
  └── return result
```

### Source-verified evidence

| File | Line | Code | Role |
|------|------|------|------|
| `agent/turn_context.py` | 322-333 | `invoke_hook("pre_llm_call", ...)` | **Only call site** — no other file invokes this hook |
| `agent/conversation_loop.py` | 508 | `_ctx = build_turn_context(...)` | Called once before the while loop |
| `agent/conversation_loop.py` | 563 | `while (api_call_count < ...):` | Tool loop starts — no pre_llm_call inside |
| `agent/conversation_loop.py` | 717-732 | `if _plugin_user_context: _injections.append(...)` | Context reused on every iteration |

### Langfuse plugin confirmation

From `plugins/observability/langfuse/__init__.py` (lines 1028-1032):

```python
# Register for both hook name variants so the plugin works across
# Hermes versions.  pre_api_request / post_api_request fire per API
# call (preferred); pre_llm_call / post_llm_call fire once per turn.
ctx.register_hook("pre_api_request", on_pre_llm_request)
ctx.register_hook("post_api_request", on_post_llm_call)
```

### Why this matters

If you register a `pre_llm_call` hook expecting it to fire on every API call
(e.g., to count tokens or trace per-iteration data), you will only see it fire
once. Use `pre_api_request` / `post_api_request` for per-iteration observability.

| Need | Use This Hook |
|------|---------------|
| Context injection into user message | `pre_llm_call` (once per turn) |
| Per-API-call tracing/observability | `pre_api_request` / `post_api_request` |
| Tool execution blocking | `pre_tool_call` |
| Post-turn analysis | `post_llm_call` (once per turn) |

## Key Source Landmarks

### 1. Hook invocation (`turn_context.py:318–343`)

```python
# Plugin hook: pre_llm_call (context injected into user message, not system prompt).
plugin_user_context = ""
try:
    from hermes_cli.plugins import invoke_hook as _invoke_hook
    _pre_results = _invoke_hook(
        "pre_llm_call",
        session_id=agent.session_id,
        task_id=effective_task_id,
        turn_id=turn_id,
        user_message=original_user_message,
        conversation_history=list(messages),
        is_first_turn=(not bool(conversation_history)),
        model=agent.model,
        platform=getattr(agent, "platform", None) or "",
        sender_id=getattr(agent, "_user_id", None) or "",
    )
    _ctx_parts: list[str] = []
    for r in _pre_results:
        if isinstance(r, dict) and r.get("context"):
            _ctx_parts.append(str(r["context"]))
        elif isinstance(r, str) and r.strip():
            _ctx_parts.append(r)
    if _ctx_parts:
        plugin_user_context = "\n\n".join(_ctx_parts)
except Exception as exc:
    logger.warning("pre_llm_call hook failed: %s", exc)
```

**Key behaviors:**
- Returns can be `{"context": "..."}` OR a plain string
- Multiple plugins' contexts are **merged** with `"\n\n"`
- Order follows plugin discovery order (alphabetical by directory name)
- The resulting string is stored in `TurnContext.plugin_user_context`

### 2. Ephemeral injection into API message (`conversation_loop.py:712–732`)

```python
# Inject ephemeral context into the current turn's user message.
# Sources: memory manager prefetch + plugin pre_llm_call hooks
# Both are API-call-time only — original message never mutated.
if idx == current_turn_user_idx and msg.get("role") == "user":
    _injections = []
    if _ext_prefetch_cache:
        _injections.append(_ext_prefetch_cache)
    if _plugin_user_context:
        _injections.append(_plugin_user_context)
    if _injections:
        _base = api_msg.get("content", "")
        api_msg["content"] = _base + "\n\n" + "\n\n".join(_injections)
```

**Key behaviors:**
- The original `messages` list is **never mutated** — only the API-copy gets the injection
- Changes are **ephemeral** — not persisted to session DB, not visible in logs
- Memory prefetch context is injected **before** plugin context

### 3. TurnContext definition (`turn_context.py:58–59`)

```python
@dataclass
class TurnContext:
    # ...
    # Context contributed by ``pre_llm_call`` plugins (appended to user message).
    plugin_user_context: str = ""
```

## Return-Value Formats

Both formats are accepted:

```python
# Dict format (recommended)
return {"context": "Additional text to append"}

# Plain string format (also works)
return "Additional text to append"
```

## Kwargs Received

```python
kwargs = {
    "session_id": str,
    "task_id": str,
    "turn_id": str,
    "user_message": str,                # The original user message text
    "conversation_history": list,       # Full message list (read-only)
    "is_first_turn": bool,
    "model": str,
    "platform": str,                    # "cli", "telegram", "discord", etc.
    "sender_id": str,                   # User identifier
}
```

## Comparison With Other Injection Mechanisms

| Mechanism | When | Scope | Persisted? | Use Case |
|-----------|------|-------|-----------|----------|
| `pre_llm_call` return `{"context"}` | Before API call (once per turn) | All platforms | No (ephemeral) | RAG, guardrails, suffix injection, memory prefetch |
| `ctx.inject_message()` | Mid-conversation (interrupt queue) | All platforms | Yes (appears next turn) | Recovery prompts, timed injections |
| `pre_gateway_dispatch` `"rewrite"` | Gateway message dispatch | Gateway only | Yes (rewrites source text) | Content filtering, message transformation |
| `register_middleware` | System prompt modification | All platforms | Depends | Middleware patterns |
| `transform_tool_result` | After tool execution | All platforms | Ephemeral | Output masking, annotation |

## Example: Suffix Injection Plugin

A complete working example of a plugin that appends a custom suffix to every
user message:

```python
"""
user-suffix-plugin — appends a configurable suffix to every user message
before it is sent to the LLM.
"""

from typing import Any

def _cfg() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        return load_config().get("plugins", {}).get("user_suffix_plugin", {})
    except Exception:
        return {}

def _enabled() -> bool:
    return _cfg().get("enabled", True)

def _suffix() -> str:
    return _cfg().get("suffix", "\n\nPlease respond in Japanese.")

def _on_pre_llm_call(user_message: str = "", **kwargs) -> dict[str, str] | None:
    if not _enabled():
        return None
    suffix = _suffix()
    if not suffix:
        return None
    return {"context": suffix}

def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
```

**config.yaml** entry:
```yaml
plugins:
  enabled:
    - user-suffix-plugin
  user_suffix_plugin:
    enabled: true
    suffix: "\n\nPlease respond in Japanese."
```

## Pitfalls

| Pitfall | Solution |
|---------|----------|
| Context not appearing in session logs | It's ephemeral by design — only sent at API-call time |
| Context only visible in first turn | Works every turn — check `_enabled()` and hook registration |
| Only one plugin's context appears | All plugins' contexts are merged with `\n\n` — check other plugins |
| `{"context": ""}` still adds a blank line | Return `None` instead of an empty context |
| Gateway users don't see the suffix | Suffix is in the API call, not in the visible transcript — intentional |
| Hook only fires once per turn (expected) | Use `pre_api_request` if you need per-API-call interception |
| Unexpected return from `invoke_hook` | Check return type: list of non-None values from all callbacks |
