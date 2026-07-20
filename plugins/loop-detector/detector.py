"""
detector.py — Loop detection algorithms for loop-detector plugin v2.0.0.

Pure, dependency-free module (no hermes imports): normalization + detection
functions only.
"""

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Detection:
    """Represents a detected loop.

    Attributes:
        kind:     Classification of the loop (e.g. ``"tool_loop_consecutive"``,
                  ``"tool_loop_window"``, ``"tool_loop_alternating"``).
        pattern:  The unique identifier for the detected pattern — for tool
                  loops this is the normalized tool call
                  ``(tool_name, canonical_json)``, for alternating patterns
                  it is the period sequence ``list[tuple[str, str]]``.
        detail:   Human-readable description of the detection.
    """

    kind: str
    pattern: object
    detail: str


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_tool_call(tool_name: str, args: dict[str, Any]) -> tuple[str, str]:
    """Normalize a tool call by stripping volatile keys and sorting JSON keys.

    Volatile keys removed: ``task_id``, ``session_id``, ``tool_call_id``.
    Returns ``(tool_name, canonical_json)``.
    """
    filtered = {
        k: v
        for k, v in args.items()
        if k not in ("task_id", "session_id", "tool_call_id")
    }
    canonical = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return (tool_name, canonical)


def normalize_text(text: str) -> str:
    """Normalize text for response-loop similarity comparison.

    Performs (in order):
      1. Lowercasing
      2. Whitespace collapse (any run of whitespace → single space)
      3. Digit sequences → ``{NUM}``
      4. Code-fence language specifier removal (`````python`` → `````)
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b\d+\b", "{NUM}", text)
    text = re.sub(r"```\w+", "```", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Text similarity (internal helper)
# ---------------------------------------------------------------------------


def _text_similarity(text1: str, text2: str) -> float:
    """Compute ``difflib.SequenceMatcher.ratio()`` on normalized texts."""
    n1 = normalize_text(text1)
    n2 = normalize_text(text2)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


# ---------------------------------------------------------------------------
# Tool-loop detection
# ---------------------------------------------------------------------------


def _check_alternating(
    entries: list[tuple[str, str]], period: int
) -> list[tuple[str, str]] | None:
    """Check if ``entries`` form a repeating cycle of ``period``.

    Returns the period pattern (the first ``period`` unique entries) on
    match, or ``None``.  A valid match requires:
      - At least two full periods
      - ``len(entries)`` is an exact multiple of ``period`` (no partial cycle)
      - Pattern entries are not all identical
    """
    n = len(entries)
    if n < period * 2 or n % period != 0:
        return None

    pattern = entries[:period]

    for i in range(n - period):
        if entries[i] != entries[i + period]:
            return None

    # Must not be all identical — that would be consecutive, not alternating
    if len(set(pattern)) < 2:
        return None

    return pattern


def detect_tool_loop(
    history: list[tuple[str, str]],
    current: tuple[str, str],
    *,
    consecutive_threshold: int = 3,
    window_size: int = 10,
    window_threshold: int = 4,
    alternating_enabled: bool = True,
    alternating_min_length: int = 6,
) -> Detection | None:
    """Detect tool-call loops.

    ``current`` is **not** yet in ``history`` — detection happens before
    append (SPEC §4.2).  Three checks are performed in order; the first
    matching one is returned.

    Checks
    ------
    1. **Consecutive** — the same normalized tool call appears
       ``consecutive_threshold`` times in a row ending at ``current``.
    2. **Window** — ``current`` appears ``>= window_threshold`` times in the
       last ``window_size`` calls (history tail ``window_size - 1`` plus
       ``current``).
    3. **Alternating** (if enabled) — period-2 or period-3 repeating sequence
       spanning exactly ``alternating_min_length`` calls.  Period 2 is tried
       before period 3; only complete cycles are accepted (no partial
       trailing cycle).  All identical entries do not qualify.
    """
    # -- 1. Consecutive match ------------------------------------------------
    needed = max(0, consecutive_threshold - 1)
    if needed > 0 and len(history) >= needed:
        if all(h == current for h in history[-needed:]):
            return Detection(
                kind="tool_loop_consecutive",
                pattern=current,
                detail=(
                    f"Same normalized tool call {consecutive_threshold} times "
                    f"consecutively: {current}"
                ),
            )

    # -- 2. Window repetition ------------------------------------------------
    check_window = history[-(window_size - 1) :] + [current]
    count = check_window.count(current)
    if count >= window_threshold:
        return Detection(
            kind="tool_loop_window",
            pattern=current,
            detail=(
                f"Same normalized tool call appeared {count} times in last "
                f"{min(len(history) + 1, window_size)} calls: {current}"
            ),
        )

    # -- 3. Alternating pattern ----------------------------------------------
    if alternating_enabled and len(history) + 1 >= alternating_min_length:
        candidates = history[-(alternating_min_length - 1) :] + [current]
        if len(candidates) == alternating_min_length:
            # Period 2 first (SPEC §4.2 — smaller period takes priority)
            match = _check_alternating(candidates, period=2)
            if match is not None:
                return Detection(
                    kind="tool_loop_alternating",
                    pattern=match,
                    detail=(
                        f"Alternating pattern (period 2) over last "
                        f"{alternating_min_length} calls: {match}"
                    ),
                )
            # Then period 3
            match = _check_alternating(candidates, period=3)
            if match is not None:
                return Detection(
                    kind="tool_loop_alternating",
                    pattern=match,
                    detail=(
                        f"Alternating pattern (period 3) over last "
                        f"{alternating_min_length} calls: {match}"
                    ),
                )

    return None


# ---------------------------------------------------------------------------
# Response-loop detection
# ---------------------------------------------------------------------------


def detect_response_loop(
    responses: list[str],
    *,
    similarity_threshold: float = 0.85,
    window_size: int = 5,
    min_repetitions: int = 2,
) -> int | None:
    """Detect response loops using text similarity.

    Normalises each of the last ``window_size`` responses, computes
    ``difflib.SequenceMatcher.ratio()`` on every adjacent pair, and returns
    the index in ``responses`` where the first qualifying consecutive run of
    similar pairs begins.  Returns ``None`` when no loop is found.

    ``min_repetitions`` is clamped to ``window_size - 1`` if the caller
    provides a larger value (SPEC §5.2).
    """
    min_repetitions = min(min_repetitions, window_size - 1)

    if len(responses) < window_size or min_repetitions < 1:
        return None

    recent = responses[-window_size:]
    normalized = [normalize_text(r) for r in recent]

    current_streak = 0
    streak_start: int | None = None

    for i in range(len(normalized) - 1):
        n1, n2 = normalized[i], normalized[i + 1]
        if not n1 and not n2:
            sim = 1.0
        elif not n1 or not n2:
            sim = 0.0
        else:
            sim = _text_similarity(recent[i], recent[i + 1])

        if sim >= similarity_threshold:
            current_streak += 1
            if streak_start is None:
                streak_start = i
            if current_streak >= min_repetitions:
                return len(responses) - window_size + streak_start
        else:
            current_streak = 0
            streak_start = None

    return None
