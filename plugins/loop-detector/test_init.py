"""Validation tests for __init__.py per SPEC v2.0.0.

Run with: python3 test_init.py
"""

import importlib
import importlib.util
import os
import sys
import types

sys.path.insert(0, os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Module loader — loads __init__.py as a package so relative imports work
# ---------------------------------------------------------------------------


def _load_plugin():
    """Load ``loop_detector`` package from ``__init__.py``."""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_name = "loop_detector"

    # Register sub-modules first so relative imports in __init__.py resolve.
    for sub in ("detector", "confirmation"):
        spec = importlib.util.spec_from_file_location(
            f"{pkg_name}.{sub}", os.path.join(pkg_dir, f"{sub}.py")
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{pkg_name}.{sub}"] = mod
        spec.loader.exec_module(mod)

    # Register & load the package itself.
    spec = importlib.util.spec_from_file_location(
        pkg_name, os.path.join(pkg_dir, "__init__.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[pkg_name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_plugin()

# Alias frequently-used names.
_on_pre_tool_call = mod._on_pre_tool_call
_on_post_api_request = mod._on_post_api_request
_on_pre_llm_call = mod._on_pre_llm_call
_on_session_reset = mod._on_session_reset
_llm_request_middleware = mod._llm_request_middleware

# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------

passed = 0
failed = 0


def check(label: str, ok: bool) -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


# ---------------------------------------------------------------------------
# Fake Hermes plugin context
# ---------------------------------------------------------------------------


class _FakeStructuredResult:
    """Stub for PluginLlmStructuredResult."""

    def __init__(self, *, parsed: object = None, content_type: str = "text"):
        self.parsed = parsed
        self.content_type = content_type


class _FakeAssistantMessage:
    """Stub for NormalizedResponse with a .content attribute."""

    def __init__(self, content: str):
        self.content = content


class _FakeLlm:
    """Stub for ctx.llm with configurable structured result."""

    def __init__(self, confirm_is_loop: bool = True):
        self.confirm_is_loop = confirm_is_loop
        self.calls: list[dict[str, object]] = []

    def complete_structured(
        self, *, instructions: str, input: object, json_schema: object, timeout: float
    ) -> _FakeStructuredResult:
        self.calls.append(
            {"instructions": instructions, "input": input, "schema": json_schema}
        )
        return _FakeStructuredResult(
            parsed={"is_loop": self.confirm_is_loop, "reason": "test-reason"},
            content_type="json",
        )


class _FakeCtx:
    """Stub Hermes plugin context."""

    def __init__(self, confirm_is_loop: bool = True):
        self.llm = _FakeLlm(confirm_is_loop=confirm_is_loop)
        self.hooks: dict[str, object] = {}
        self.middlewares: dict[str, object] = {}

    def register_hook(self, name: str, handler: object) -> None:
        self.hooks[name] = handler

    def register_middleware(self, name: str, handler: object) -> None:
        self.middlewares[name] = handler


# ---------------------------------------------------------------------------
# Config patches
# ---------------------------------------------------------------------------


def _make_config(**overrides: object) -> dict[str, object]:
    """Build a default config dict with optional overrides."""
    base: dict[str, object] = {
        "enabled": True,
        "tool_loop": {
            "enabled": True,
            "consecutive_threshold": 3,
            "window_size": 10,
            "window_threshold": 4,
            "alternating_enabled": True,
            "alternating_min_length": 6,
        },
        "response_loop": {
            "enabled": True,
            "similarity_threshold": 0.95,
            "window_size": 10,
            "min_repetitions": 3,
        },
        "confirmation": {
            "enabled": True,
            "on_error": "block",
            "timeout": 30,
        },
        "response": {
            "max_blocks_per_session": 5,
            "recovery_notice": "",
        },
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NORMALIZED_A = ("read_file", '{"path": "/tmp/x"}')
NORMALIZED_B = ("write_file", '{"content": "hi", "path": "/tmp/y"}')


def _reset():
    """Reset module state between test scenarios."""
    mod._state.clear()
    mod._ctx = None


def _setup_response_loop_detection(
    session_id: str = "s_rl",
    text: str = "Let me analyze the code.",
    count: int = 4,
) -> None:
    """Pre-populate similar responses to trigger response-loop detection.

    With ``min_repetitions=3``, sending ``count`` identical responses will
    trigger detection on the last one (trailing run of count-1 >= 3).
    """
    for _ in range(count):
        _on_post_api_request(
            session_id=session_id,
            assistant_message=_FakeAssistantMessage(text),
        )


# =====================================================================
# 1. Three identical pre_tool_call → 3rd returns block dict
# =====================================================================
print("\n=== 1. Three identical pre_tool_call → 3rd returns block dict ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Call 1: no detection yet (only 1 in history).
r1 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s1")
check("call 1 returns None", r1 is None)

# Call 2: no detection yet (only 2 consecutive, threshold=3).
r2 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s1")
check("call 2 returns None", r2 is None)

# Call 3: 3 consecutive → detection → confirmation → block.
r3 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s1")
check("call 3 returns dict", isinstance(r3, dict))
if isinstance(r3, dict):
    check("call 3 action is block", r3.get("action") == "block")
    check("call 3 has message", isinstance(r3.get("message"), str))
    check("block message mentions loop", "Loop" in r3.get("message", ""))

# Verify state.
s1_state = mod._get_or_create_state("s1")
check("block_count is 1", s1_state["block_count"] == 1)
check(
    "tool_calls has 2 entries (blocked call not appended)",
    len(s1_state["tool_calls"]) == 2,
)
if len(s1_state["tool_calls"]) == 2:
    check(
        "tool_calls contains correct entries",
        list(s1_state["tool_calls"]) == [NORMALIZED_A, NORMALIZED_A],
    )

# Verify blocked_this_turn has the pattern.
check(
    "blocked_this_turn has the loop key",
    len(s1_state["blocked_this_turn"]) == 1,
)

# Verify pending_recovery was set for next turn.
check(
    "pending_recovery is set (for next turn's pre_llm_call)",
    s1_state["pending_recovery"] is not None,
)

# =====================================================================
# 2. Allowlisted pattern passes after intentional verdict
# =====================================================================
print("\n=== 2. Allowlisted pattern passes after intentional verdict ===\n")

_reset()
# Use a FakeLlm that returns False (intentional) for the first confirmation.
ctx = _FakeCtx(confirm_is_loop=False)
mod._ctx = ctx

# Call 1: no detection.
r1 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s2")
check("call 1 returns None (no detection)", r1 is None)

# Call 2: no detection (only 2 consecutive, threshold=3).
r2 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s2")
check("call 2 returns None (no detection)", r2 is None)

# Call 3: detection → confirmation returns False (intentional) → allowlisted.
r3 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s2")
check("call 3 returns None (allowlisted)", r3 is None)
check("allowlist has the pattern key (confirmation was called)", bool(ctx.llm.calls))

check("confirmation was asked exactly once", len(ctx.llm.calls) == 1)

# Verify pattern was added to allowlist.
s2_state = mod._get_or_create_state("s2")
loop_key = mod.make_allowlist_key(
    "tool_loop_consecutive",
    mod.Detection(kind="tool_loop_consecutive", pattern=NORMALIZED_A, detail="test"),
)
check("allowlist contains pattern", s2_state["allowlist"].contains(loop_key))

# Call 4: same call again → allowlisted → no block, no confirmation.
pre_confirm_calls = len(ctx.llm.calls)
r4 = _on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s2")
check("call 4 returns None (allowlisted)", r4 is None)
check("no extra confirmation call", len(ctx.llm.calls) == pre_confirm_calls)

# Verify tool_calls has 4 entries (all appended since no block).
check(
    "tool_calls has 4 entries",
    len(s2_state["tool_calls"]) == 4,
)

# =====================================================================
# 3. pending_recovery delivered once on next pre_llm_call
# =====================================================================
print("\n=== 3. pending_recovery delivered once on next pre_llm_call ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Trigger a block (3 consecutive calls).
_on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s3")
_on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s3")
r_block = _on_pre_tool_call(
    tool_name="read_file", args={"path": "/tmp/x"}, session_id="s3"
)
check(
    "block was triggered",
    isinstance(r_block, dict) and r_block.get("action") == "block",
)

s3_state = mod._get_or_create_state("s3")
check("pending_recovery is set", s3_state["pending_recovery"] is not None)

# Simulate next turn: pre_llm_call should deliver the recovery notice.
r_recovery = _on_pre_llm_call(session_id="s3")
check("pre_llm_call returns context dict", isinstance(r_recovery, dict))
if isinstance(r_recovery, dict):
    check("context key is present", "context" in r_recovery)
    check("context message is non-empty", bool(r_recovery.get("context", "")))

check("pending_recovery cleared after delivery", s3_state["pending_recovery"] is None)

# Second pre_llm_call: no more recovery.
r_no_recovery = _on_pre_llm_call(session_id="s3")
check("second pre_llm_call returns None", r_no_recovery is None)

# Also verify blocked_this_turn was cleared by pre_llm_call.
check(
    "blocked_this_turn is empty (cleared by pre_llm_call)",
    len(s3_state["blocked_this_turn"]) == 0,
)

# =====================================================================
# 4. block_count cap switches to recovery-only
# =====================================================================
print("\n=== 4. block_count cap switches to recovery-only ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

s4_state = mod._get_or_create_state("s4")

# Start with block_count at max (5).  Now all detections should be
# recovery-only (no blocking) per SPEC §7.2.
s4_state["block_count"] = 5
s4_state["tool_calls"].clear()

# With consecutive_threshold=3, the 3rd identical call triggers detection.
# Since block_count (5) >= max_blocks_per_session (5), the detection should
# set pending_recovery and NOT block.

# Call 1: first A → no detection (history empty) → append
r1 = _on_pre_tool_call(tool_name="tool_a", args={}, session_id="s4")
check("cap: call 1 returns None (history empty)", r1 is None)

# Call 2: second A → consecutive needs 3, only 2 → no detection → append
r2 = _on_pre_tool_call(tool_name="tool_a", args={}, session_id="s4")
check("cap: call 2 returns None (2 consecutive < threshold 3)", r2 is None)

# Call 3: third A → consecutive detection! block_count (5) >= max (5) → recovery-only.
r3 = _on_pre_tool_call(tool_name="tool_a", args={}, session_id="s4")
check("cap: call 3 returns None (recovery-only, no block)", r3 is None)
check("cap: block_count unchanged (still 5)", s4_state["block_count"] == 5)
check("cap: pending_recovery is now set", s4_state["pending_recovery"] is not None)
check("cap: call was appended to history (cap mode)", len(s4_state["tool_calls"]) == 3)

# Call 4: same tool → detection again → recovery-only again
r4 = _on_pre_tool_call(tool_name="tool_a", args={}, session_id="s4")
check("cap: call 4 returns None (still recovery-only)", r4 is None)
check("cap: block_count still 5", s4_state["block_count"] == 5)

# Verify no block was ever returned.
check("cap: never blocked", r1 is None and r2 is None and r3 is None and r4 is None)

# Deliver the pending recovery via pre_llm_call.
r_recovery = _on_pre_llm_call(session_id="s4")
check(
    "cap: pending recovery delivered",
    isinstance(r_recovery, dict) and "context" in r_recovery,
)
check(
    "cap: pending_recovery cleared after delivery", s4_state["pending_recovery"] is None
)

# =====================================================================
# 5. session_reset clears state
# =====================================================================
print("\n=== 5. session_reset clears state ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Build state for two sessions.
_on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s5a")
_on_pre_tool_call(tool_name="read_file", args={"path": "/tmp/x"}, session_id="s5b")
check("s5a state exists", "s5a" in mod._state)
check("s5b state exists", "s5b" in mod._state)

# Reset s5a.
_on_session_reset(session_id="s5a")
check("s5a state removed after reset", "s5a" not in mod._state)
check("s5b state still exists", "s5b" in mod._state)

# Reset s5b with extra kwargs (SPEC §11: TUI may omit reason).
_on_session_reset(session_id="s5b", reason="/new", platform="cli")
check("s5b state removed", "s5b" not in mod._state)

# Reset non-existent session — no error.
try:
    _on_session_reset(session_id="nonexistent")
    check("reset non-existent session: no error", True)
except Exception:
    check("reset non-existent session: no error", False)

# =====================================================================
# 6. Edge: disabled config skips detection
# =====================================================================
print("\n=== 6. Edge: disabled config skips detection ===\n")

_reset()

# We'll patch _enabled to return False.
original_enabled = mod._enabled
try:
    mod._enabled = lambda: False
    mod._ctx = _FakeCtx(confirm_is_loop=True)

    # These should all return None regardless of pattern.
    for i in range(5):
        r = _on_pre_tool_call(
            tool_name="read_file", args={"path": "/tmp/x"}, session_id="s6"
        )
        check(f"disabled: call {i + 1} returns None", r is None)

    r = _on_pre_llm_call(session_id="s6")
    check("disabled: pre_llm_call returns None", r is None)

    r = _on_post_api_request(
        session_id="s6",
        assistant_message=_FakeAssistantMessage("Let me analyze the code."),
    )
    check("disabled: post_api_request returns None", r is None)

    r = _llm_request_middleware(
        request={"messages": [{"role": "user", "content": "hi"}]},
        session_id="s6",
    )
    check("disabled: llm_request middleware returns None", r is None)

    check("disabled: no state created", "s6" not in mod._state)
finally:
    mod._enabled = original_enabled

# =====================================================================
# 7. Edge: try/except guards — exception in handler returns None
# =====================================================================
print("\n=== 7. Exception safety ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Inject a state with a broken allowlist (will cause AttributeError).
mod._state["s7"] = {"broken": "state"}

try:
    r = _on_pre_tool_call(
        tool_name="read_file", args={"path": "/tmp/x"}, session_id="s7"
    )
    check("exception in pre_tool_call → returns None", r is None)

    r = _on_pre_llm_call(session_id="s7")
    check("exception in pre_llm_call → returns None", r is None)

    r = _on_post_api_request(
        session_id="s7",
        assistant_message=_FakeAssistantMessage("hello world"),
    )
    check("exception in post_api_request → returns None", r is None)

    r = _llm_request_middleware(
        request={"messages": [{"role": "user", "content": "hi"}]},
        session_id="s7",
    )
    check("exception in llm_request middleware → returns None", r is None)

    # on_session_reset on a non-dict state won't trigger exception since
    # we pop by key (key exists so pop succeeds).
    _on_session_reset(session_id="s7")
    check("exception in session_reset → no crash", True)
finally:
    _state_val = getattr(mod, "_state", {})
    _state_val.pop("s7", None)  # type: ignore[union-attr]

# =====================================================================
# 8. Register wiring
# =====================================================================
print("\n=== 8. register() wires hooks correctly ===\n")

_reset()

ctx = _FakeCtx(confirm_is_loop=True)
mod.register(ctx)

check("pre_tool_call hook registered", "pre_tool_call" in ctx.hooks)
check("post_api_request hook registered", "post_api_request" in ctx.hooks)
check("pre_llm_call hook registered", "pre_llm_call" in ctx.hooks)
check("on_session_reset hook registered", "on_session_reset" in ctx.hooks)

check("llm_request middleware registered", "llm_request" in ctx.middlewares)

# Verify _ctx was set.
check("_ctx was stored", mod._ctx is ctx)

# =====================================================================
# 9. Response-loop detection via post_api_request
# =====================================================================
print("\n=== 9. Response-loop detection via post_api_request ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

state = mod._get_or_create_state("s9")

# Call with None assistant_message → should be skipped (guard).
r = _on_post_api_request(session_id="s9", assistant_message=None)
check("post_api_request with None msg → None", r is None)

# Call with non-str content → should be skipped.
msg = _FakeAssistantMessage(content=123)  # type: ignore[arg-type]
r = _on_post_api_request(session_id="s9", assistant_message=msg)
check("post_api_request with non-str content → None", r is None)

# Call with empty string (tool-call-only) → should be skipped.
r = _on_post_api_request(
    session_id="s9",
    assistant_message=_FakeAssistantMessage(""),
)
check("post_api_request with empty content → None", r is None)

# Send 4 identical responses to trigger detection (trailing run of 3).
for i in range(4):
    r = _on_post_api_request(
        session_id="s9",
        assistant_message=_FakeAssistantMessage("Let me analyze the code."),
    )
    check(f"identical response {i + 1} → None (no block on response loop)", r is None)

# After 4 identical responses, trailing run of pairs = 3 >= min_repetitions=3 → detection.
check(
    "pending_recovery set after response loop detection",
    state["pending_recovery"] is not None,
)
check(
    "response_detected_this_turn is True",
    state["response_detected_this_turn"] is True,
)
check(
    "responses has 4 entries",
    len(state["assistant_responses"]) == 4,
)

# Within same turn, another similar response should NOT re-detect.
pre_recovery = state["pending_recovery"]
r = _on_post_api_request(
    session_id="s9",
    assistant_message=_FakeAssistantMessage("Let me analyze the code again."),
)
check("same-turn re-detection guarded → None", r is None)
check(
    "pending_recovery unchanged after re-detection guard",
    state["pending_recovery"] is pre_recovery,
)
check(
    "response_detected_this_turn still True",
    state["response_detected_this_turn"] is True,
)

# =====================================================================
# 10. llm_request middleware injection
# =====================================================================
print("\n=== 10. llm_request middleware injection ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Trigger response-loop detection.
_setup_response_loop_detection("s10")

state = mod._get_or_create_state("s10")
check("pending_recovery set", state["pending_recovery"] is not None)

# Simulate llm_request middleware with a request dict.
original_request: dict[str, object] = {
    "messages": [{"role": "user", "content": "What's next?"}],
    "model": "gpt-4",
}
result = _llm_request_middleware(request=original_request, session_id="s10")
check("llm middleware returns dict", isinstance(result, dict))
if isinstance(result, dict):
    check("llm result has request key", "request" in result)
    modified = result["request"]
    check("modified is not original (deep copy)", modified is not original_request)
    check(
        "messages has 2 entries (original + injected)",
        len(modified["messages"]) == 2,
    )
    check(
        "injected message has user role",
        modified["messages"][1]["role"] == "user",
    )
    check(
        "injected message has non-empty content",
        bool(modified["messages"][1].get("content", "")),
    )

# pending_recovery should be None (popped by middleware).
check(
    "pending_recovery cleared after middleware injection",
    state["pending_recovery"] is None,
)

# Second middleware call → None (once-only).
result2 = _llm_request_middleware(request=original_request, session_id="s10")
check("second middleware call returns None (once-only)", result2 is None)

# Verify original request object was NOT mutated.
check(
    "original request was not mutated",
    len(original_request["messages"]) == 1,  # type: ignore[arg-type]
)

# Middleware with no session_id → None.
result3 = _llm_request_middleware(request=original_request, session_id="")
check("middleware with empty session_id → None", result3 is None)

# Middleware with None request → None.
result4 = _llm_request_middleware(request=None, session_id="s10")
check("middleware with None request → None", result4 is None)

# Middleware with request missing messages → None.
result5 = _llm_request_middleware(
    request={"model": "gpt-4"},
    session_id="s10",  # type: ignore[typeddict-item]
)
check("middleware with no messages key → None", result5 is None)

# =====================================================================
# 11. pre_llm_call fallback for response-loop recovery
# =====================================================================
print("\n=== 11. pre_llm_call fallback for response-loop recovery ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# Trigger response-loop detection WITHOUT calling llm_request middleware.
_setup_response_loop_detection("s11")

state = mod._get_or_create_state("s11")
check("pending_recovery set (pre fallback)", state["pending_recovery"] is not None)
check(
    "response_detected_this_turn True",
    state["response_detected_this_turn"] is True,
)

# pre_llm_call should deliver the recovery (fallback for last-API-call-of-turn).
r = _on_pre_llm_call(session_id="s11")
check("pre_llm_call returns context dict (fallback)", isinstance(r, dict))
if isinstance(r, dict):
    check("context key present", "context" in r)
    check("context message is non-empty", bool(r.get("context", "")))

check(
    "pending_recovery cleared after pre_llm_call delivery",
    state["pending_recovery"] is None,
)
check(
    "response_detected_this_turn cleared by pre_llm_call",
    state["response_detected_this_turn"] is False,
)
check(
    "blocked_this_turn cleared by pre_llm_call",
    len(state["blocked_this_turn"]) == 0,
)

# Second pre_llm_call → None (nothing left).
r2 = _on_pre_llm_call(session_id="s11")
check("second pre_llm_call returns None (no more recovery)", r2 is None)

# =====================================================================
# 12. Response-loop with intentional verdict (allowlisted)
# =====================================================================
print("\n=== 12. Response-loop with intentional verdict (allowlisted) ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=False)

_setup_response_loop_detection("s12")

state = mod._get_or_create_state("s12")
# With confirm_is_loop=False, the confirmation returns False (intentional).
# So pending_recovery should NOT be set.
check(
    "pending_recovery NOT set (intentional verdict)",
    state["pending_recovery"] is None,
)
check(
    "response_detected_this_turn NOT set",
    state["response_detected_this_turn"] is False,
)

# Allowlist should contain the response pattern.
check(
    "allowlist contains response pattern",
    state["allowlist"].contains("response"),
)

# =====================================================================
# 13. post_api_request with disabled response_loop
# =====================================================================
print("\n=== 13. post_api_request with disabled response_loop ===\n")

_reset()
mod._ctx = _FakeCtx(confirm_is_loop=True)

# We need to patch _cfg to return a config with response_loop disabled.
original_cfg = mod._cfg
try:
    mod._cfg = lambda: {
        "enabled": True,
        "response_loop": {"enabled": False},
        "response": {},
    }

    r = _on_post_api_request(
        session_id="s13",
        assistant_message=_FakeAssistantMessage("test"),
    )
    check("response_loop disabled → None", r is None)
finally:
    mod._cfg = original_cfg

# =====================================================================
# Summary
# =====================================================================

print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
if failed:
    sys.exit(1)
else:
    print("All tests passed!")
