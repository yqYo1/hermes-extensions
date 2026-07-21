"""confirmation.py — LLM confirmation + allowlist for loop-detector plugin v2.0.0.

SPEC §6 (LLM confirmation), §6.3 (failure handling), §6.4 (allowlist).

This module provides:
  - ``ask_llm_confirmation()`` — calls ``complete_structured`` on the
    plugin's ``ctx.llm`` object and returns ``True`` = block / ``False`` =
    allow.
  - ``Allowlist`` — in-session set of confirmed-intentional patterns.
  - ``make_allowlist_key()`` — creates a canonical key from a ``Detection``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:  # Package import (normal plugin loading)
    from .detector import Detection
except ImportError:  # Standalone import (tests run from the plugin directory)
    from detector import Detection  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Confirmation JSON schema (SPEC §6.2)
# ---------------------------------------------------------------------------

_CONFIRMATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_loop": {
            "type": "boolean",
            "description": "true if this is an unintended loop, false if intentional",
        },
        "reason": {
            "type": "string",
            "description": "brief reason for the judgment",
        },
    },
    "required": ["is_loop", "reason"],
}

# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def _build_instructions(loop_type: str, detail: str) -> str:
    """Build the instructions for the LLM confirmation call.

    Args:
        loop_type: Loop classification (e.g. ``"tool_loop_consecutive"``,
            ``"tool_loop_window"``, ``"response_loop"``).
        detail: Human-readable detection description from
            ``Detection.detail``.

    Returns:
        The ``instructions`` string to pass to
        ``ctx.llm.complete_structured()``.
    """
    return (
        "You are a loop detector operating inside an LLM agent session.\n\n"
        "A repetitive pattern has been detected. Determine whether this is "
        "an unintended loop (the model is stuck repeating the same action "
        "without making progress) or an intentional pattern (e.g. polling "
        "for CI results, waiting for a background process, periodic status "
        "checking).\n\n"
        f"Loop type: {loop_type}\n"
        f"Detection detail: {detail}\n\n"
        "Respond with a single JSON object containing:\n"
        '- "is_loop": true if this is an unintended loop, false if intentional\n'
        '- "reason": a brief explanation for the judgment'
    )


# ---------------------------------------------------------------------------
# LLM confirmation (SPEC §6)
# ---------------------------------------------------------------------------


def ask_llm_confirmation(
    ctx_llm: Any,
    loop_type: str,
    detail: str,
    *,
    timeout: int = 30,
    on_error: str = "block",
) -> bool:
    """Ask the LLM to confirm whether a detected pattern is a loop.

    Calls ``ctx_llm.complete_structured()`` with the confirmation schema
    from SPEC §6.2.

    Args:
        ctx_llm: The ``ctx.llm`` object from a Hermes plugin context
            (expected to have a ``complete_structured`` method matching
            the signature in ``plugin_llm.py``).
        loop_type: Classification of the loop (e.g. ``"tool_loop"``,
            ``"tool_loop_consecutive"``, ``"response_loop"``).
        detail: Human-readable description of the detection (from
            ``Detection.detail``).  Should include tool name, repeat
            count, and arguments summary (SPEC §6.2).
        timeout: Max seconds to wait for the confirmation call.
        on_error: Behaviour when the call fails (exception, timeout, or
            parse failure).  ``"block"`` (default, fail-closed) returns
            ``True``; ``"allow"`` (fail-open) returns ``False``.

    Returns:
        ``True`` if the pattern should be blocked (loop confirmed or
        confirmation failed with ``on_error="block"``).
        ``False`` if the pattern is intentional (should be allowed).
    """
    instructions = _build_instructions(loop_type, detail)

    try:
        result = ctx_llm.complete_structured(
            instructions=instructions,
            input=[{"type": "text", "text": detail}],
            json_schema=_CONFIRMATION_SCHEMA,
            timeout=float(timeout),
        )

        if result.content_type == "json" and isinstance(result.parsed, dict):
            is_loop = bool(result.parsed.get("is_loop", True))
            reason = str(result.parsed.get("reason", "no reason provided"))
            logger.debug(
                "[loop-detector] LLM confirmation: is_loop=%s, reason=%s",
                is_loop,
                reason,
            )
            return is_loop

        # Parse failure — content_type is not "json" or parsed is None
        logger.warning(
            "[loop-detector] LLM confirmation: parse failure "
            "(content_type=%r, parsed=%r), on_error=%r → %s",
            result.content_type,
            result.parsed,
            on_error,
            "block" if on_error == "block" else "allow",
        )
        return on_error == "block"

    except Exception as exc:
        logger.warning(
            "[loop-detector] LLM confirmation: %s: %s, on_error=%r → %s",
            type(exc).__name__,
            exc,
            on_error,
            "block" if on_error == "block" else "allow",
        )
        return on_error == "block"


# ---------------------------------------------------------------------------
# Allowlist (SPEC §6.4)
# ---------------------------------------------------------------------------


class Allowlist:
    """In-session allowlist of confirmed-intentional patterns.

    SPEC §6.4: patterns judged intentional by the LLM are registered here
    so that subsequent occurrences skip confirmation and blocking.

    Pattern keys:
    - Tool loops (consecutive / window): the normalized tool-call tuple
      ``(tool_name, canonical_json)``.
    - Tool loops (alternating): the period sequence
      ``list[tuple[str, str]]``.
    - Response loops: the fixed string ``"response"``.
    """

    MAX_ENTRIES = 256  # Cap to prevent unbounded growth.

    def __init__(self) -> None:
        self._patterns: dict[object, None] = {}  # dict as ordered set (Python 3.7+)

    def add(self, pattern: object) -> None:
        """Register a pattern as confirmed-intentional.

        Args:
            pattern: Canonical pattern key (tuple, list, or string).
        """
        if len(self._patterns) >= self.MAX_ENTRIES:
            # Evict oldest entry to prevent unbounded growth.
            self._patterns.pop(next(iter(self._patterns)))
        self._patterns[pattern] = None

    def contains(self, pattern: object) -> bool:
        """Check if a pattern has already been allowed.

        Args:
            pattern: Canonical pattern key to look up.

        Returns:
            ``True`` if the pattern was previously confirmed as intentional.
        """
        return pattern in self._patterns

    def remove(self, pattern: object) -> None:
        """Remove a pattern from the allowlist."""
        self._patterns.pop(pattern, None)

    def clear(self) -> None:
        """Clear all allowed patterns."""
        self._patterns.clear()

    def snapshot(self) -> frozenset[object]:
        """Return an immutable snapshot of the current allowlist contents."""
        return frozenset(self._patterns)


def make_allowlist_key(
    loop_type: str,
    detection: Detection | None = None,
) -> object:
    """Create a canonical allowlist key from a loop type and optional detection.

    SPEC §6.4 defines pattern keys as:
    - Tool loops → the detection's ``pattern`` attribute (either the
      ``(tool_name, canonical_json)`` tuple or the period sequence list).
    - Response loops → the string ``"response"``.

    Args:
        loop_type: Loop classification (e.g. ``"tool_loop_consecutive"``,
            ``"response_loop"``).
        detection: The ``Detection`` instance, if available (required for
            tool loops).

    Returns:
        A hashable object suitable as an allowlist key, or ``None`` if the
        loop type is unrecognised.
    """
    if detection is not None and loop_type.startswith("tool_loop"):
        return detection.pattern
    if loop_type == "response_loop":
        return "response"
    return loop_type
