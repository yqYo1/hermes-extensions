"""__init__.py — Loop detector plugin v2.0.0 for Hermes Agent.

SPEC v2.0.0: hook wiring + session state + block/notify flow.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

# Support both relative (package) and direct (standalone test) import paths.
try:
    from .detector import (
        Detection,
        detect_response_loop,
        detect_tool_loop,
        normalize_tool_call,
    )  # type: ignore[attr-defined]
    from .confirmation import Allowlist, ask_llm_confirmation, make_allowlist_key  # type: ignore[attr-defined]
except ImportError:
    from detector import (
        Detection,
        detect_response_loop,
        detect_tool_loop,
        normalize_tool_call,
    )
    from confirmation import Allowlist, ask_llm_confirmation, make_allowlist_key

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_ctx: Any = None  # Plugin context — set by register() (SPEC §9.3)
_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Config helpers (SPEC §10)
# ---------------------------------------------------------------------------


def _cfg() -> dict[str, Any]:
    """Load ``plugins.loop_detector`` from config with safe fallback."""
    try:
        from hermes_cli.config import load_config

        return load_config().get("plugins", {}).get("loop_detector", {})
    except Exception:
        return {}


def _enabled() -> bool:
    return _cfg().get("enabled", True)


def _tool_cfg() -> dict[str, Any]:
    return _cfg().get("tool_loop", {})


def _response_cfg() -> dict[str, Any]:
    return _cfg().get("response_loop", {})


def _confirm_cfg() -> dict[str, Any]:
    return _cfg().get("confirmation", {})


def _response_cfg() -> dict[str, Any]:
    return _cfg().get("response", {})


# ---------------------------------------------------------------------------
# Session state — SPEC §9.1
# ---------------------------------------------------------------------------


def _make_default_state() -> dict[str, Any]:
    return {
        "tool_calls": deque(maxlen=50),
        "assistant_responses": deque(maxlen=20),
        "allowlist": Allowlist(),
        "block_count": 0,
        "pending_recovery": None,
        "blocked_this_turn": set(),
    }


def _get_or_create_state(session_id: str) -> dict[str, Any]:
    """Return the state dict for *session_id*, creating it if absent."""
    with _lock:
        if session_id not in _state:
            _state[session_id] = _make_default_state()
        return _state[session_id]


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

_DEFAULT_RECOVERY_NOTICE = (
    "[システム通知] 前回のターンでループが検出・ブロックされました。\n"
    "検出パターン: {summary}\n\n"
    "同じ推論や同じツール呼び出しを繰り返さず、別のアプローチを検討してください。\n"
    "すでに試行済みの内容は省略し、次のステップに進んでください。"
)


def _build_block_message(
    detection: Detection,
    block_count: int,
    max_blocks: int = 5,
) -> str:
    """Build the block message for a tool-loop detection (SPEC §7.1)."""
    return (
        f"[loop-detector] Loop detected: {detection.detail}. "
        f"Blocked ({block_count}/{max_blocks}). "
        "Do not repeat the same call; try a different approach."
    )


def _build_recovery_notice(detection: Detection) -> str:
    """Build recovery-notice text (SPEC §8.3), overridable by config."""
    override = _response_cfg().get("recovery_notice", "")
    if override:
        return override
    return _DEFAULT_RECOVERY_NOTICE.format(summary=detection.detail)


def _build_response_recovery_notice() -> str:
    """Build recovery notice for a response-loop detection (SPEC §8.3)."""
    override = _response_cfg().get("recovery_notice", "")
    if override:
        return override
    return _DEFAULT_RECOVERY_NOTICE.format(
        summary="response loop (similar responses repeated)"
    )


# ---------------------------------------------------------------------------
# Hook: pre_tool_call — tool-loop detection & block (SPEC §4, §7)
# ---------------------------------------------------------------------------


def _on_pre_tool_call(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    session_id: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    """Handle ``pre_tool_call``.

    Returns ``{"action": "block", "message": ...}`` when a loop is detected
    and confirmed; returns ``None`` otherwise.
    """
    try:
        if not _enabled() or not session_id:
            return None

        state = _get_or_create_state(session_id)

        tcfg = _tool_cfg()
        if not tcfg.get("enabled", True):
            return None

        current = normalize_tool_call(tool_name, args or {})

        # Detect BEFORE appending (SPEC §4.2 — current not in history yet).
        detection = detect_tool_loop(
            list(state["tool_calls"]),
            current,
            consecutive_threshold=tcfg.get("consecutive_threshold", 3),
            window_size=tcfg.get("window_size", 10),
            window_threshold=tcfg.get("window_threshold", 4),
            alternating_enabled=tcfg.get("alternating_enabled", True),
            alternating_min_length=tcfg.get("alternating_min_length", 6),
        )

        if detection is None:
            # No detection — append to history, let the call proceed.
            state["tool_calls"].append(current)
            return None

        # ── Detection occurred ──────────────────────────────────────────
        loop_key = make_allowlist_key(detection.kind, detection)
        max_blocks = _response_cfg().get("max_blocks_per_session", 5)

        # Allowlisted — skip (SPEC §6.4).
        if state["allowlist"].contains(loop_key):
            state["tool_calls"].append(current)
            return None

        # Block-count cap exceeded — recovery-only (SPEC §7.2).
        # Must precede the blocked_this_turn check: once the cap is reached,
        # no further blocks are issued for ANY detection, including
        # same-turn repeats.
        if state["block_count"] >= max_blocks:
            state["pending_recovery"] = _build_recovery_notice(detection)
            state["tool_calls"].append(current)
            return None

        # Already blocked this turn — block immediately (SPEC §6.4).
        if loop_key in state["blocked_this_turn"]:
            state["block_count"] += 1
            state["pending_recovery"] = _build_recovery_notice(detection)
            return {
                "action": "block",
                "message": _build_block_message(
                    detection, state["block_count"], max_blocks
                ),
            }

        # ── LLM confirmation (SPEC §6) ──────────────────────────────────
        ccfg = _confirm_cfg()
        if ccfg.get("enabled", True):
            is_loop = ask_llm_confirmation(
                _ctx.llm,
                detection.kind,
                detection.detail,
                timeout=ccfg.get("timeout", 30),
                on_error=ccfg.get("on_error", "block"),
            )

            if not is_loop:
                # Intentional — allowlist, append, let it through.
                state["allowlist"].add(loop_key)
                state["tool_calls"].append(current)
                return None

        # ── Block (loop confirmed or confirmation disabled) (SPEC §7.1) ─
        state["block_count"] += 1
        state["blocked_this_turn"].add(loop_key)
        state["pending_recovery"] = _build_recovery_notice(detection)
        # Blocked calls are NOT appended to history (SPEC §7.1).
        return {
            "action": "block",
            "message": _build_block_message(
                detection, state["block_count"], max_blocks
            ),
        }

    except Exception:
        # SPEC §11: plugin exceptions never stop core.
        return None


# ---------------------------------------------------------------------------
# Hook: post_llm_call — response-loop detection (SPEC §5)
# ---------------------------------------------------------------------------


def _on_post_llm_call(
    session_id: str = "",
    assistant_response: str | None = None,
    **kwargs: Any,
) -> None:
    """Handle ``post_llm_call`` — record response and check for response loops.

    Never blocks; sets ``pending_recovery`` for next turn on detection.
    """
    try:
        if not _enabled() or not session_id:
            return None

        state = _get_or_create_state(session_id)

        tcfg = _response_cfg()
        if not tcfg.get("enabled", True):
            return None

        # Guard empty response (SPEC §5: won't fire for empty, but guard).
        if not assistant_response:
            return None

        # Record.
        state["assistant_responses"].append(assistant_response)

        # Detect.
        result = detect_response_loop(
            list(state["assistant_responses"]),
            similarity_threshold=tcfg.get("similarity_threshold", 0.85),
            window_size=tcfg.get("window_size", 5),
            min_repetitions=tcfg.get("min_repetitions", 2),
        )

        if result is None:
            return None

        # Allowlisted?
        response_key = make_allowlist_key("response_loop")
        if state["allowlist"].contains(response_key):
            return None

        # ── LLM confirmation for response loop ──────────────────────────
        ccfg = _confirm_cfg()
        if ccfg.get("enabled", True):
            is_loop = ask_llm_confirmation(
                _ctx.llm,
                "response_loop",
                f"Response loop detected at response index {result}",
                timeout=ccfg.get("timeout", 30),
                on_error=ccfg.get("on_error", "block"),
            )

            if not is_loop:
                state["allowlist"].add(response_key)
                return None

        # Loop confirmed — set recovery notice (SPEC §8.3).  Never block.
        state["pending_recovery"] = _build_response_recovery_notice()
        return None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Hook: pre_llm_call — recovery-notice injection (SPEC §8)
# ---------------------------------------------------------------------------


def _on_pre_llm_call(
    session_id: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    """Handle ``pre_llm_call``.

    Clears ``blocked_this_turn`` and delivers ``pending_recovery`` once.
    """
    try:
        if not _enabled() or not session_id:
            return None

        state = _get_or_create_state(session_id)

        # Clear per-turn block set (SPEC §9.1: cleared at start of next turn).
        state["blocked_this_turn"].clear()

        # Deliver pending recovery exactly once.
        recovery = state["pending_recovery"]
        if recovery is not None:
            state["pending_recovery"] = None
            return {"context": recovery}

        return None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Hook: on_session_reset — state cleanup (SPEC §9.2)
# ---------------------------------------------------------------------------


def _on_session_reset(
    session_id: str = "",
    **kwargs: Any,
) -> None:
    """Handle ``on_session_reset`` — remove session state.

    ``reason`` and other optional kwargs are accessed safely via
    ``kwargs.get()`` (SPEC §11: TUI gateway may omit ``reason``).
    """
    try:
        if not session_id:
            return None
        with _lock:
            _state.pop(session_id, None)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Plugin registration (SPEC §9.3)
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register loop-detector hooks with the plugin context."""
    global _ctx
    _ctx = ctx

    if not _enabled():
        print("[loop-detector] disabled in config, skipping registration.")
        return

    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("on_session_reset", _on_session_reset)

    print("[loop-detector] registered (v2.0.0).")
