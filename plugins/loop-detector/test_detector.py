"""
Validation tests for detector.py per SPEC v2.0.0.

Run with: python3 test_detector.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from detector import (
    Detection,
    detect_tool_loop,
    detect_response_loop,
    normalize_text,
    normalize_tool_call,
)

passed = 0
failed = 0

A = ("read_file", '{"path": "/tmp/x"}')
B = ("write_file", '{"content": "hi", "path": "/tmp/y"}')
C = ("list_dir", '{"path": "/tmp"}')

# These have different args but same tool name — still different normalized calls
A2 = ("read_file", '{"path": "/tmp/z"}')

# A normalized call with volatile keys (should be stripped)
ARGS_WITH_VOLATILE = {
    "path": "/tmp/x",
    "task_id": "t1",
    "session_id": "s1",
    "tool_call_id": "c1",
}
A_WITH_VOLATILE = ("read_file", '{"path": "/tmp/x"}')


def check(desc: str, ok: bool):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {desc}")
    else:
        failed += 1
        print(f"  FAIL  {desc}")


# =========================================================================
# normalize_tool_call
# =========================================================================
print("\n=== normalize_tool_call ===")

result = normalize_tool_call("read_file", {"path": "/tmp/x"})
check("tool_name preserved", result[0] == "read_file")
check("canonical JSON is sorted", result[1] == '{"path": "/tmp/x"}')

result2 = normalize_tool_call(
    "read_file",
    {"path": "/tmp/x", "task_id": "t1", "session_id": "s1", "tool_call_id": "c1"},
)
check("volatile keys stripped", result == result2)

# =========================================================================
# normalize_text
# =========================================================================
print("\n=== normalize_text ===")

check("empty string", normalize_text("") == "")
check("lowercase", normalize_text("Hello World") == "hello world")
check("whitespace collapse", normalize_text("a   b\t\tc\n\nd") == "a b c d")
check("digits to {NUM}", normalize_text("line 42 of 100") == "line {NUM} of {NUM}")
check("code fence language removed", normalize_text("```python\ncode") == "``` code")
check(
    "multiple code fence langs",
    normalize_text("```javascript and ```bash") == "``` and ```",
)
check("fence without lang unchanged", normalize_text("```\ncode") == "``` code")
check("strip leading/trailing space", normalize_text("  hello  ") == "hello")

# =========================================================================
# detect_tool_loop — consecutive
# =========================================================================
print("\n=== detect_tool_loop — consecutive ===")

# Threshold 3: need 2 history matches + current = 3 in a row
h = [A, B, A, A]  # last 2 = A, A
result = detect_tool_loop(h, A, consecutive_threshold=3)
check(
    "consecutive: 3 in a row",
    result is not None and result.kind == "tool_loop_consecutive",
)

# Not enough consecutive
h = [A, B, A, B]
result = detect_tool_loop(h, A, consecutive_threshold=3)
check("consecutive: not enough", result is None)

# Threshold 4: need 3 history matches
h = [A, A, A, A]
result = detect_tool_loop(h, A, consecutive_threshold=4)
check(
    "consecutive: 4 in a row",
    result is not None and result.kind == "tool_loop_consecutive",
)

# Threshold 2: trivial case
h = [A]
result = detect_tool_loop(h, A, consecutive_threshold=2)
check(
    "consecutive: threshold=2",
    result is not None and result.kind == "tool_loop_consecutive",
)

# =========================================================================
# detect_tool_loop — window
# =========================================================================
print("\n=== detect_tool_loop — window ===")

# history has 9 entries, 3 of them are A. Current is A → 4 in window.
h = [B, A, B, A, B, A, C, C, C]
result = detect_tool_loop(h, A, window_size=10, window_threshold=4)
check(
    "window: A appears 4 times in last 10",
    result is not None and result.kind == "tool_loop_window",
)

# A only appears 3 times including current — below threshold of 4
h = [B, A, B, A, C, C, C]
result = detect_tool_loop(h, A, window_size=10, window_threshold=4)
check("window: below threshold", result is None)

# Window threshold with small window
# history[-3:] = [B, A, B]; + [A] = [B, A, B, A]; count(A) = 2 < 3 → no match
h = [A, B, A, B]
result = detect_tool_loop(h, A, window_size=4, window_threshold=3)
check("window: not enough As in small window", result is None)

# Window threshold with enough As for small window
# Note: consecutive detection (threshold=3 default) catches [A, A] + A first
h = [A, B, A, A]
result = detect_tool_loop(h, A, window_size=4, window_threshold=3)
check("window: exact match in small window (consecutive)", result is not None)
check(
    "window: detected as consecutive (priority)",
    result is not None and result.kind == "tool_loop_consecutive",
)

# Window detection without consecutive interference: interleaved calls
h = [A, B, A, C, A, C, A]
result = detect_tool_loop(h, A, window_size=5, window_threshold=3)
check(
    "window: interleaved detection (pure window)",
    result is not None and result.kind == "tool_loop_window",
)

# =========================================================================
# detect_tool_loop — off-by-one guard (current not double-counted)
# =========================================================================
print("\n=== detect_tool_loop — off-by-one ===")

# Critical: current is NOT in history. The check_window is built as
# history[-(window_size-1):] + [current] without mutating history.
# This verifies the detection correctly counts current only once.
h = [B, A, C, A]
result = detect_tool_loop(h, A, window_size=5, window_threshold=3)
check(
    "off-by-one: correct count (current not in history init)",
    result is not None and result.kind == "tool_loop_window",
)

# Consecutive catches this first, which is also correct
h = [A, A]
result = detect_tool_loop(h, A, window_size=3, window_threshold=3)
check("off-by-one: correct detection with 3 As in window", result is not None)
check(
    "off-by-one: detected as consecutive (correct)",
    result is not None and result.kind == "tool_loop_consecutive",
)

# =========================================================================
# detect_tool_loop — alternating period 2
# =========================================================================
print("\n=== detect_tool_loop — alternating period 2 ===")

# A,B,A,B,A,B with alternating_min_length=6
h = [A, B, A, B, A]
result = detect_tool_loop(h, B, alternating_min_length=6)
check(
    "alternating p2: A,B,A,B,A,B",
    result is not None and result.kind == "tool_loop_alternating",
)
if result:
    check("alternating p2: pattern is [A, B]", result.pattern == [A, B])

# Incomplete cycle: A,B,A,B,A (5 entries, missing B to complete)
h = [A, B, A, B]
result = detect_tool_loop(h, A, alternating_min_length=5)
check(
    "alternating p2: incomplete cycle (5 entries, period 2) = NO MATCH", result is None
)

# Single element repeating (not alternating, should be caught by consecutive first but also
# should NOT match alternating due to all-identical check)
h = [A, A, A, A, A]
result = detect_tool_loop(
    h, A, consecutive_threshold=6, window_threshold=6, alternating_min_length=6
)
# consecutive should catch it first
if result is not None:
    check(
        "alternating: all-identical caught by consecutive first",
        result.kind == "tool_loop_consecutive",
    )

# Period-2 but with only 1 complete cycle (should NOT match — need >= 2 periods)
h = [A, B, A]
result = detect_tool_loop(h, B, alternating_min_length=4)
# alternating_min_length=4, but only 4 entries: [A, B, A, B], which is 2 cycles of period 2
# Wait, len(history)=3, +1 for current = 4. candidates=[A,B,A,B]. n=4, period=2, n%2=0, n>=4.
# pattern=[A,B], check entries[0]==entries[2]=A==A ✓, entries[1]==entries[3]=B==B ✓
# So it DOES match. That's at least 2 full periods.
check(
    "alternating p2: 2 full cycles",
    result is not None and result.kind == "tool_loop_alternating",
)

# Period 2 with 3 different elements (should NOT match)
h = [A, B, A, C, A]
result = detect_tool_loop(h, B, alternating_min_length=6)
check("alternating p2: pattern broken = NO MATCH", result is None)

# =========================================================================
# detect_tool_loop — alternating period 3
# =========================================================================
print("\n=== detect_tool_loop — alternating period 3 ===")

# A,B,C,A,B,C with alternating_min_length=6
h = [A, B, C, A, B]
result = detect_tool_loop(h, C, alternating_min_length=6)
check(
    "alternating p3: A,B,C,A,B,C",
    result is not None and result.kind == "tool_loop_alternating",
)
if result:
    check("alternating p3: pattern is [A, B, C]", result.pattern == [A, B, C])

# Incomplete cycle: A,B,C,A,B (5 entries, period 3 → not a multiple)
h = [A, B, C, A]
result = detect_tool_loop(h, B, alternating_min_length=5)
check("alternating p3: incomplete cycle = NO MATCH", result is None)

# Period 3 broken
h = [A, B, C, A, B, A]
result = detect_tool_loop(h, C, alternating_min_length=6)
check("alternating p3: broken pattern = NO MATCH", result is None)

# =========================================================================
# detect_tool_loop — period 2 takes priority over period 3
# =========================================================================
print("\n=== detect_tool_loop — period 2 before period 3 ===")

# A,B,A,B,A,B also matches period 3 (A,B,A repeated twice)
# Period 2 should be detected first
h = [A, B, A, B, A]
result = detect_tool_loop(h, B, alternating_min_length=6)
check(
    "p2 priority: period 2 detected (not period 3)",
    result is not None and result.kind == "tool_loop_alternating",
)
if result:
    check("p2 priority: pattern is [A, B]", result.pattern == [A, B])

# =========================================================================
# detect_tool_loop — alternating disabled
# =========================================================================
print("\n=== detect_tool_loop — alternating disabled ===")

h = [A, B, A, B, A]
result = detect_tool_loop(h, B, alternating_enabled=False, alternating_min_length=6)
check("alternating disabled: None", result is None)

# =========================================================================
# detect_response_loop
# =========================================================================
print("\n=== detect_response_loop ===")

# Near-identical responses — should detect
responses = [
    "Let me analyze the code.",
    "Let me analyze the code.",
    "Let me analyze the code again.",
    "Let me analyze the code more.",
    "I think the answer is 42.",
]
result = detect_response_loop(
    responses, similarity_threshold=0.5, window_size=5, min_repetitions=3
)
# responses[-5:] are all 5 entries. Pairs:
# (0,1): "let me analyze the code." vs "let me analyze the code." → very similar
# (1,2): "let me analyze the code." vs "let me analyze the code again." → similar
# (2,3): "let me analyze the code again." vs "let me analyze the code more." → similar
# (3,4): "let me analyze the code more." vs "i think the answer is {num}." → different
# Streak of 3, min_repetitions=3 → detect at index 0
check("response: near-identical streak of 3", result is not None)
if result is not None:
    check("response: start index is 0", result == 0)

# Different responses — should NOT detect
responses = [
    "First analysis.",
    "Second analysis.",
    "Third analysis.",
    "Fourth analysis.",
    "Done.",
]
result = detect_response_loop(
    responses, similarity_threshold=0.9, window_size=5, min_repetitions=2
)
check("response: all different = None", result is None)

# Exactly at threshold
responses = [
    "Hello world",
    "Hello world",
    "Something else",
    "Hello world",
    "Hello world",
]
result = detect_response_loop(
    responses, similarity_threshold=1.0, window_size=5, min_repetitions=2
)
# pairs (0,1) and (3,4) are identical → 1.0, but they're not consecutive
# (0,1) = 1.0, but (1,2) breaks → streak resets. Then (2,3) breaks, (3,4)=1.0 → streak=1, not enough
check("response: non-consecutive similar pairs = None", result is None)

# Consecutive identical pairs at the end
responses = [
    "A",
    "B",
    "C",
    "D",
    "D",
]
result = detect_response_loop(
    responses, similarity_threshold=0.9, window_size=5, min_repetitions=1
)
check("response: single pair at end, min_reps=1", result is not None)
if result is not None:
    check("response: start index is 3", result == 3)

# =========================================================================
# detect_response_loop — min_repetitions clamping
# =========================================================================
print("\n=== detect_response_loop — min_repetitions clamping ===")

resp = ["a", "b", "c", "d", "e"]
# window_size=5 → max pairs = 4 → clamp min_repetitions to 4
result = detect_response_loop(resp, window_size=5, min_repetitions=10)
# After clamping: min_repetitions=4, which is > (5-1)=4, no wait, min(10, 4) = 4
# So it clamps to 4. With 5 entries, there are only 4 adjacent pairs.
# Our entries are all different, so max streak = 0.
check("clamping: returns None with all different", result is None)

# Verify clamping: provide responses that are all identical, window_size=5
# With min_repetitions=10, it should clamp to 4
resp = ["same"] * 5
result = detect_response_loop(
    resp, similarity_threshold=0.0, window_size=5, min_repetitions=10
)
# Clamped: min_repetitions=4. All 5 responses are "same", so normalized is ["same"]*5
# Pairs (0,1),(1,2),(2,3),(3,4) all have sim >= 0.0 → streak=4 ≥ 4
# Start at index 0 (within window), mapped back: len(resp)-5+0 = 0
check("clamping: threshold reached with clamped value", result is not None)
if result is not None:
    check("clamping: start index is 0", result == 0)

# window_size=2, min_repetitions=2 → clamp to 1
resp = ["x", "y"]
result = detect_response_loop(resp, window_size=2, min_repetitions=2)
# Clamped: min_repetitions = min(2, 1) = 1. 2 entries → 1 adjacent pair.
# Pair (0,1) with similarity ~0 (different) → no match → None
check("clamping: window=2, reps=2 clamped to 1, different = None", result is None)

resp = ["hello", "hello"]
result = detect_response_loop(
    resp, similarity_threshold=0.9, window_size=2, min_repetitions=2
)
# Clamped: min_repetitions=1. Pair (0,1) = 1.0 ≥ 0.9 → streak=1 ≥ 1
# Start at index 0 within window → len-2+0 = 0
check("clamping: window=2, same response detected", result is not None and result == 0)

# =========================================================================
# detect_response_loop — not enough data
# =========================================================================
print("\n=== detect_response_loop — not enough data ===")

result = detect_response_loop(["a", "b"], window_size=5, min_repetitions=2)
check("insufficient data: None", result is None)

result = detect_response_loop([], window_size=5, min_repetitions=2)
check("empty list: None", result is None)

# =========================================================================
# Summary
# =========================================================================
print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
if failed:
    sys.exit(1)
else:
    print("All tests passed!")
