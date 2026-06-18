import json
import re
import threading
from typing import Any

from .detector import detect_thinking_loop, detect_tool_loop, normalize_tool_call
from .rollback import perform_rollback


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------


def _cfg() -> dict[str, Any]:
    """config.yaml の plugins.loop_detector セクションを取得"""
    try:
        from hermes_cli.config import load_config

        return load_config().get("plugins", {}).get("loop_detector", {})
    except Exception:
        return {}


def _enabled() -> bool:
    return _cfg().get("enabled", True)


def _thinking_cfg() -> dict[str, Any]:
    return _cfg().get("thinking_loop", {})


def _tool_cfg() -> dict[str, Any]:
    return _cfg().get("tool_loop", {})


def _rollback_cfg() -> dict[str, Any]:
    return _cfg().get("rollback", {})


def _confirm_cfg() -> dict[str, Any]:
    return _cfg().get("confirmation", {})


def _max_retries() -> int:
    return _rollback_cfg().get("max_retries", 3)


def _recovery_prompt() -> str:
    default = (
        "[system notification]\n"
        "前回の試行でループが検知されました。以下に注意してください:\n"
        "- 同じ推論や同じツール呼び出しを繰り返さないでください\n"
        "- 異なるアプローチや別のツールを検討してください\n"
        "- すでに試行済みの内容は省略し、次のステップに進んでください"
    )
    return _rollback_cfg().get("recovery_prompt", default)


# ---------------------------------------------------------------------------
# セッション状態
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def _get_state(sid: str) -> dict[str, Any]:
    with _lock:
        return _state.setdefault(
            sid,
            {
                "assistant_messages": [],
                "tool_calls": [],
                "retry_count": 0,
                "pending_confirmation": None,
            },
        )


def _reset_state(sid: str) -> None:
    with _lock:
        _state.pop(sid, None)


# ---------------------------------------------------------------------------
# LLM確認プロンプト（構造的応答）
# ---------------------------------------------------------------------------

_CONFIRMATION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_loop": {
            "type": "boolean",
            "description": "true if this is an unintended loop, false if intentional",
        },
        "reason": {"type": "string", "description": "brief reason for the judgment"},
    },
    "required": ["is_loop", "reason"],
}


def _build_confirmation_prompt(loop_type: str, details: str) -> str:
    """LLM確認用プロンプト。JSON形式の応答を要求。"""
    return (
        f"[loop-detector confirmation request]\n"
        f"The following repetitive pattern was detected:\n"
        f"- Type: {loop_type}\n"
        f"- Details: {details}\n\n"
        f"Is this an unintended loop, or is it intentional (e.g., waiting for CI, polling)?\n"
        f"Respond with JSON only: {json.dumps(_CONFIRMATION_SCHEMA, ensure_ascii=False)}\n"
        f'Example: {{"is_loop": true, "reason": "same reasoning repeated without progress"}}'
    )


# ---------------------------------------------------------------------------
# LLM確認実行
# ---------------------------------------------------------------------------


def _ask_llm_confirmation(ctx, loop_type: str, details: str) -> bool:
    """
    LLMに確認を投げ、構造的な応答を解析。
    Returns: True = ループ判定（ブロック/巻き戻しすべき）, False = 意図的（許可）
    """
    prompt = _build_confirmation_prompt(loop_type, details)

    try:
        llm = ctx.llm
        if not llm:
            return True

        response = llm.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )

        content = (
            response.get("content", "") if isinstance(response, dict) else str(response)
        )

        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content)
            is_loop = result.get("is_loop", True)
            reason = result.get("reason", "no reason provided")

            print(
                f"[loop-detector] LLM confirmation: is_loop={is_loop}, reason={reason}"
            )
            return is_loop
        except (json.JSONDecodeError, AttributeError):
            print(
                "[loop-detector] Failed to parse LLM response, defaulting to loop=True"
            )
            return True

    except Exception as e:
        print(f"[loop-detector] LLM confirmation failed: {e}, defaulting to loop=True")
        return True


# ---------------------------------------------------------------------------
# フック
# ---------------------------------------------------------------------------


def _on_post_llm_call(
    session_id: str = "", assistant_message: dict[str, Any] | None = None, **kwargs
):
    """assistant メッセージを記録し、思考ループを検知→確認"""
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

    if not _confirm_cfg().get("enabled", True):
        _execute_rollback(session_id, loop_start, kwargs.get("ctx"), "thinking")
        return

    details = f"messages[{loop_start}:] show similar reasoning patterns"
    ctx = kwargs.get("ctx")
    if ctx and _ask_llm_confirmation(ctx, "thinking_loop", details):
        _execute_rollback(session_id, loop_start, ctx, "thinking")


def _on_pre_tool_call(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    session_id: str = "",
    **kwargs,
):
    """ツール呼び出しを記録し、ツールループを検知→確認→ブロック"""
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

    if not _confirm_cfg().get("enabled", True):
        return _execute_tool_block(session_id, loop_start, tool_name, kwargs.get("ctx"))

    details = f"tool '{tool_name}' called repeatedly with similar arguments"
    ctx = kwargs.get("ctx")
    if ctx and _ask_llm_confirmation(ctx, "tool_loop", details):
        return _execute_tool_block(session_id, loop_start, tool_name, ctx)

    return None


# ---------------------------------------------------------------------------
# 実行アクション
# ---------------------------------------------------------------------------


def _execute_rollback(session_id: str, loop_start: int, ctx, loop_type: str) -> None:
    """思考ループ検知時の巻き戻し"""
    state = _get_state(session_id)

    if state["retry_count"] >= _max_retries():
        print(f"[loop-detector] {loop_type} loop at {loop_start}, max retries reached.")
        return

    state["retry_count"] += 1
    print(
        f"[loop-detector] {loop_type} loop at {loop_start}, "
        f"retry {state['retry_count']}/{_max_retries()}"
    )

    if ctx:
        perform_rollback(session_id, loop_start, ctx, _recovery_prompt())


def _execute_tool_block(
    session_id: str, loop_start: int, tool_name: str, ctx
) -> dict[str, str]:
    """ツールループ検知時のブロック"""
    state = _get_state(session_id)

    if state["retry_count"] >= _max_retries():
        return {
            "action": "block",
            "message": f"[loop-detector] Tool loop ({tool_name}). Max retries reached.",
        }

    state["retry_count"] += 1
    print(
        f"[loop-detector] Tool loop at {loop_start}, "
        f"retry {state['retry_count']}/{_max_retries()}"
    )

    if ctx:
        perform_rollback(session_id, loop_start, ctx, _recovery_prompt())

    return {
        "action": "block",
        "message": (
            f"[loop-detector] Loop detected: repeated '{tool_name}' calls. "
            f"Retry {state['retry_count']}/{_max_retries()}. "
            "Please try a different approach."
        ),
    }


# ---------------------------------------------------------------------------
# セッション境界
# ---------------------------------------------------------------------------


def _on_session_end(session_id: str = "", **kwargs) -> None:
    if session_id:
        _reset_state(session_id)


def _on_session_reset(session_id: str = "", **kwargs) -> None:
    if session_id:
        _reset_state(session_id)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    if not _enabled():
        print("[loop-detector] disabled in config.")
        return

    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("on_session_reset", _on_session_reset)

    print("[loop-detector] registered (v1.1.0 with LLM confirmation).")
