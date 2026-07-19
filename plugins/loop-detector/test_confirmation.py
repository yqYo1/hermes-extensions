"""Validation tests for confirmation.py per SPEC v2.0.0.

Run with: python3 test_confirmation.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from confirmation import (
    ask_llm_confirmation,
    Allowlist,
    make_allowlist_key,
)
from detector import Detection

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
# Fake LLM stub
# ---------------------------------------------------------------------------


class FakeStructuredResult:
    """Stub for PluginLlmStructuredResult."""

    def __init__(self, *, parsed=None, content_type: str = "text"):
        self.parsed = parsed
        self.content_type = content_type


class FakeLlm:
    """Stub for ctx.llm with configurable result or exception."""

    def __init__(self, result=None, raise_exc: type[Exception] | None = None):
        self._result = result
        self._raise_exc = raise_exc

    def complete_structured(self, *, instructions, input, json_schema, timeout):
        if self._raise_exc is not None:
            raise self._raise_exc("fake error for testing")
        return self._result


# ---------------------------------------------------------------------------
# Tests: ask_llm_confirmation
# ---------------------------------------------------------------------------

print("=== ask_llm_confirmation ===\n")

# --- 1. Loop verdict ---
print("--- loop verdict ---")

llm = FakeLlm(
    result=FakeStructuredResult(
        parsed={"is_loop": True, "reason": "same tool call repeated 5 times"},
        content_type="json",
    )
)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_consecutive",
    detail="Same normalized tool call 3 times: ('read_file', '{\"path\": \"/tmp/x\"}')",
    timeout=10,
)
check("is_loop=True → returns True", result is True)

# --- 2. Intentional verdict ---
print("\n--- intentional verdict ---")

llm = FakeLlm(
    result=FakeStructuredResult(
        parsed={"is_loop": False, "reason": "polling for CI result"},
        content_type="json",
    )
)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_consecutive",
    detail="Same normalized tool call 3 times: ('terminal', '{\"command\": \"curl ...\"}')",
    timeout=10,
)
check("is_loop=False → returns False", result is False)

# --- 3. Exception with on_error=block ---
print("\n--- exception with on_error='block' ---")

llm = FakeLlm(raise_exc=RuntimeError)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_consecutive",
    detail="test detail",
    timeout=10,
    on_error="block",
)
check("exception + on_error='block' → True", result is True)

# --- 4. Exception with on_error=allow ---
print("\n--- exception with on_error='allow' ---")

llm = FakeLlm(raise_exc=TimeoutError)
result = ask_llm_confirmation(
    llm,
    loop_type="thinking_loop",
    detail="test detail",
    timeout=1,
    on_error="allow",
)
check("exception + on_error='allow' → False", result is False)

# --- 5. Parsed=None (parse failure) ---
print("\n--- parsed=None (parse failure) ---")

# content_type != "json" with parsed=None
llm = FakeLlm(
    result=FakeStructuredResult(parsed=None, content_type="text"),
)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_window",
    detail="test detail",
    timeout=10,
    on_error="block",
)
check("parsed=None + on_error='block' → True", result is True)

# on_error='allow' variant
llm = FakeLlm(
    result=FakeStructuredResult(parsed=None, content_type="text"),
)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_window",
    detail="test detail",
    timeout=10,
    on_error="allow",
)
check("parsed=None + on_error='allow' → False", result is False)

# content_type="json" but parsed=None
llm = FakeLlm(
    result=FakeStructuredResult(parsed=None, content_type="json"),
)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_window",
    detail="test detail",
    timeout=10,
    on_error="block",
)
check("content_type='json' + parsed=None → True (on_error='block')", result is True)

# --- 6. Default on_error is 'block' ---
print("\n--- default on_error ---")

llm = FakeLlm(raise_exc=ValueError)
result = ask_llm_confirmation(
    llm,
    loop_type="tool_loop_consecutive",
    detail="test detail",
    timeout=10,
)
check("exception + default on_error → True (block)", result is True)

# ---------------------------------------------------------------------------
# Tests: Allowlist
# ---------------------------------------------------------------------------

print("\n\n=== Allowlist ===\n")

wl = Allowlist()
check("new allowlist is empty", len(wl.snapshot()) == 0)
check("empty allowlist does not contain anything", wl.contains("anything") is False)

pattern_a = ("read_file", '{"path": "/tmp/x"}')
pattern_b = ("write_file", '{"content": "hi"}')
thinking_pattern = "thinking"

wl.add(pattern_a)
check("contains pattern_a after add", wl.contains(pattern_a) is True)
check("does not contain pattern_b", wl.contains(pattern_b) is False)
check("snapshot includes pattern_a", pattern_a in wl.snapshot())
check("snapshot excludes pattern_b", pattern_b not in wl.snapshot())

wl.add(thinking_pattern)
check("contains thinking pattern", wl.contains(thinking_pattern) is True)

wl.remove(pattern_a)
check("pattern_a removed", wl.contains(pattern_a) is False)
check("thinking_pattern still present", wl.contains(thinking_pattern) is True)

wl.clear()
check("empty after clear", len(wl.snapshot()) == 0)

# ---------------------------------------------------------------------------
# Tests: make_allowlist_key
# ---------------------------------------------------------------------------

print("\n=== make_allowlist_key ===\n")

# Tool loop — pattern is the normalized tuple
tool_detection = Detection(
    kind="tool_loop_consecutive",
    pattern=("read_file", '{"path": "/tmp/x"}'),
    detail="test",
)
key = make_allowlist_key("tool_loop_consecutive", tool_detection)
check("tool_loop key is detection.pattern", key == ("read_file", '{"path": "/tmp/x"}'))

# Tool loop window
key = make_allowlist_key("tool_loop_window", tool_detection)
check(
    "tool_loop_window key is detection.pattern",
    key == ("read_file", '{"path": "/tmp/x"}'),
)

# Alternating pattern
alt_detection = Detection(
    kind="tool_loop_alternating",
    pattern=[("read_file", '{"path": "/tmp/x"}'), ("write_file", '{"content": "hi"}')],
    detail="test",
)
key = make_allowlist_key("tool_loop_alternating", alt_detection)
check("alternating key is period sequence", isinstance(key, list))
if isinstance(key, list):
    check("period sequence length is 2", len(key) == 2)

# Thinking loop
key = make_allowlist_key("thinking_loop")
check("thinking_loop key is 'thinking'", key == "thinking")

# Unknown loop type
key = make_allowlist_key("unknown_loop")
check("unknown loop type returns the type string", key == "unknown_loop")

# Tool loop without detection — falls back to loop_type string
key = make_allowlist_key("tool_loop_consecutive", None)
check(
    "tool_loop without detection falls back to loop_type string",
    key == "tool_loop_consecutive",
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
