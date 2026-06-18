"""
Loop detector plugin template — detects thinking loops and tool-call loops.
Copy and modify for your own loop-detection needs.
"""

import difflib
import json
import re
import threading
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from hermes_cli.config import get_config


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _cfg() -> Dict[str, Any]:
    return get_config().get("plugins", {}).get("loop_detector", {})


def _enabled() -> bool:
    return _cfg().get("enabled", True)


def _thinking_cfg() -> Dict[str, Any]:
    return _cfg().get("thinking_loop", {})


def _tool_cfg() -> Dict[str, Any]:
    return _cfg().get("tool_loop", {})


def _rollback_cfg() -> Dict[str, Any]:
    return _cfg().get("rollback", {})


def _max_retries() -> int:
    return _rollback_cfg().get("max_retries", 3)


def _recovery_prompt() -> str:
    default = (
        "[system notification]\n"
        "Loop detected. Please try a different approach and avoid repeating the same reasoning or tool calls."
    )
    return _rollback_cfg().get("recovery_prompt", default)


# ---------------------------------------------------------------------------
# Session State (thread-safe)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state: Dict[str, Dict[str, Any]] = {}


def _get_state(sid: str) -> Dict[str, Any]:
    with _lock:
        return _state.setdefault(
            sid,
            {
                "assistant_messages": [],
                "tool_calls": [],
                "retry_count": 0,
            },
        )


def _reset_state(sid: str) -> None:
    with _lock:
        _state.pop(sid, None)


# ---------------------------------------------------------------------------
# Detection Logic
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b\d+\b", "{NUM}", text)
    text = re.sub(r"```\w+", "```", text)
    think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if think_match:
        text = think_match.group(1)
    return text.strip()


def text_similarity(text1: str, text2: str) -> float:
    n1 = normalize_text(text1)
    n2 = normalize_text(text2)
    if not n1 or not n2:
        return 0.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def normalize_tool_call(tool_name: str, args: Dict[str, Any]) -> Tuple[str, str]:
    filtered = {
        k: v
        for k, v in args.items()
        if k not in ("task_id", "session_id", "tool_call_id")
    }
    sorted_args = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return (tool_name, sorted_args)


def detect_thinking_loop(
    messages: List[str],
    window_size: int = 5,
    threshold: float = 0.85,
    min_repetitions: int = 2,
) -> Optional[int]:
    if len(messages) < window_size:
        return None
    recent = messages[-window_size:]
    similar_streak = 0
    loop_start = None
    for i in range(len(recent) - 1):
        sim = text_similarity(recent[i], recent[i + 1])
        if sim >= threshold:
            similar_streak += 1
            if loop_start is None:
                loop_start = max(0, len(messages) - window_size + i)
        else:
            similar_streak = 0
            loop_start = None
        if similar_streak >= min_repetitions:
            return loop_start
    return None


def detect_tool_loop(
    tool_calls: List[Tuple[str, str]],
    window_size: int = 6,
    max_identical: int = 2,
) -> Optional[int]:
    if len(tool_calls) < window_size:
        return None
    recent = tool_calls[-window_size:]
    counts = Counter(recent)
    for tc, count in counts.items():
        if count > max_identical:
            for i, call in enumerate(tool_calls):
                if call == tc:
                    return i
    if len(recent) >= 4:
        for period in range(2, len(recent) // 2 + 1):
            pattern = recent[:period]
            is_repeating = True
            for i in range(period, len(recent), period):
                chunk = recent[i : i + period]
                if len(chunk) < period:
                    break
                if chunk != pattern:
                    is_repeating = False
                    break
            if is_repeating:
                return len(tool_calls) - len(recent)
    return None


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def perform_rollback(
    session_id: str, loop_start_index: int, ctx, recovery_prompt: str
) -> bool:
    import os
    import sqlite3
    from hermes_cli.config import get_hermes_home

    print(
        f"[loop-detector] Rolling back session {session_id} to index {loop_start_index}"
    )

    try:
        from hermes_state import SessionDB

        db = SessionDB()
        messages = db.get_messages(session_id)
    except Exception:
        messages = []

    if not messages:
        db_path = os.path.join(get_hermes_home(), "state.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%message%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            try:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                )
                messages = [dict(row) for row in cursor.fetchall()]
                break
            except Exception:
                pass
        conn.close()

    if not messages or loop_start_index >= len(messages):
        return False

    cutoff = messages[loop_start_index]
    msg_id = cutoff.get("id")
    if not msg_id:
        return False

    db_path = os.path.join(get_hermes_home(), "state.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%message%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    deleted = False
    for table in tables:
        try:
            cursor.execute(
                f"DELETE FROM {table} WHERE session_id = ? AND id >= ?",
                (session_id, msg_id),
            )
            if cursor.rowcount > 0:
                deleted = True
        except Exception:
            pass
    conn.commit()
    conn.close()

    if not deleted:
        return False

    try:
        ctx.inject_message(recovery_prompt, role="user")
        return True
    except Exception as e:
        print(f"[loop-detector] Failed to inject recovery: {e}")
        return False


# ---------------------------------------------------------------------------
# Hook Handlers
# ---------------------------------------------------------------------------


def _on_post_llm_call(session_id: str = "", assistant_message: Dict = None, **kwargs):
    if not _enabled() or not session_id or not assistant_message:
        return
    content = assistant_message.get("content", "")
    if not content:
        return
    state = _get_state(session_id)
    state["assistant_messages"].append(content)
    tc = _thinking_cfg()
    if not tc.get("enabled", True):
        return
    loop_start = detect_thinking_loop(
        state["assistant_messages"],
        window_size=tc.get("window_size", 5),
        threshold=tc.get("similarity_threshold", 0.85),
        min_repetitions=tc.get("min_repetitions", 2),
    )
    if loop_start is None:
        return
    if state["retry_count"] >= _max_retries():
        print(f"[loop-detector] Loop at {loop_start}, max retries reached.")
        return
    state["retry_count"] += 1
    print(
        f"[loop-detector] Loop at {loop_start}, retry {state['retry_count']}/{_max_retries()}"
    )
    ctx = kwargs.get("ctx")
    if ctx:
        perform_rollback(session_id, loop_start, ctx, _recovery_prompt())


def _on_pre_tool_call(
    tool_name: str = "", args: Dict = None, session_id: str = "", **kwargs
):
    if not _enabled() or not session_id:
        return None
    state = _get_state(session_id)
    tc = normalize_tool_call(tool_name, args or {})
    state["tool_calls"].append(tc)
    tcfg = _tool_cfg()
    if not tcfg.get("enabled", True):
        return None
    loop_start = detect_tool_loop(
        state["tool_calls"],
        window_size=tcfg.get("window_size", 6),
        max_identical=tcfg.get("max_identical_calls", 2),
    )
    if loop_start is None:
        return None
    if state["retry_count"] >= _max_retries():
        return {
            "action": "block",
            "message": f"[loop-detector] Tool loop ({tool_name}). Max retries reached.",
        }
    state["retry_count"] += 1
    return {
        "action": "block",
        "message": (
            f"[loop-detector] Loop: repeated '{tool_name}' calls. "
            f"Retry {state['retry_count']}/{_max_retries()}. Try a different approach."
        ),
    }


def _on_session_end(session_id: str = "", **kwargs):
    if session_id:
        _reset_state(session_id)


def _on_session_reset(session_id: str = "", **kwargs):
    if session_id:
        _reset_state(session_id)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(ctx):
    if not _enabled():
        print("[loop-detector] disabled.")
        return
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_session_reset", _on_session_reset)
    print("[loop-detector] registered.")
