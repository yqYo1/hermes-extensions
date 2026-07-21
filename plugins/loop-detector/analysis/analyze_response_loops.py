#!/usr/bin/env python3
"""
analyze_response_loops.py — Read-only analysis of response-loop data from local Hermes session DB.

Purpose
-------
Extract response-loop data from the local Hermes session database for threshold
validation and loop investigation.  This is the LOG-DEPENDENT counterpart to
the stub-based CI tests — it requires a real state.db with historical sessions.

READ-ONLY
---------
This script NEVER writes to the database.  It opens in read-only mode
(sqlite3 URI mode=ro) and only performs SELECT queries.

Usage
-----
  # List candidate sessions (most assistant messages first)
  python3 analyze_response_loops.py list-sessions --limit 10

  # Extract detailed stats for a specific session
  python3 analyze_response_loops.py extract --session-id <id>

  # Run tail-anchored validation across ALL sessions
  python3 analyze_response_loops.py validate --threshold 0.95 --min-repetitions 3

  # Override the default DB path
  python3 analyze_response_loops.py list-sessions --db /custom/path/state.db

Requires a local Hermes state.db (default ~/.hermes/state.db).
Not suitable for CI — requires real session data.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sqlite3
import statistics
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Normalization — duplicated from plugins/loop-detector/detector.py
# (import via sys.path is fragile when running from arbitrary cwd; kept in
#  sync with detector.py::normalize_text)
# ---------------------------------------------------------------------------


def normalize_text(text: str, max_chars: int = 4000) -> str:
    """Normalize text for response-loop similarity comparison.

    Performs (in order):
      1. Cap at max_chars (safeguard for very long responses)
      2. Lowercasing
      3. Whitespace collapse (any run of whitespace -> single space)
      4. Digit sequences -> ``{NUM}``
      5. Code-fence language specifier removal (`````python`` -> `````)
    """
    if not text:
        return ""
    text = text[:max_chars]
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b\d+\b", "{NUM}", text)
    text = re.sub(r"```\w+", "```", text)
    return text.strip()


def text_similarity(text1: str, text2: str) -> float:
    """Compute difflib.SequenceMatcher.ratio() on normalized texts."""
    n1 = normalize_text(text1)
    n2 = normalize_text(text2)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


# ---------------------------------------------------------------------------
# Tail-anchored (trailing-run) detection — mirrors SPEC §5.2 / detector.py
# ---------------------------------------------------------------------------


def detect_response_loop(
    responses: list[str],
    *,
    similarity_threshold: float = 0.95,
    window_size: int = 10,
    min_repetitions: int = 3,
) -> int | None:
    """Tail-anchored response-loop detection (SPEC §5.2).

    Returns the index in ``responses`` where the trailing similar run begins,
    or ``None`` when no ongoing loop is found.
    """
    min_repetitions = min(min_repetitions, window_size - 1)

    if len(responses) < 2 or min_repetitions < 1:
        return None

    recent = responses[-window_size:]
    normalized = [normalize_text(r) for r in recent]

    trailing = 0
    for i in range(len(normalized) - 2, -1, -1):
        n1, n2 = normalized[i], normalized[i + 1]
        if not n1 and not n2:
            sim = 1.0
        elif not n1 or not n2:
            sim = 0.0
        else:
            sim = text_similarity(recent[i], recent[i + 1])

        if sim >= similarity_threshold:
            trailing += 1
        else:
            break

    if trailing >= min_repetitions:
        run_start_in_recent = (len(normalized) - 1) - trailing
        return len(responses) - len(recent) + max(0, run_start_in_recent)

    return None


def trailing_run_length(
    responses: list[str], *, similarity_threshold: float = 0.95
) -> int:
    """Count consecutive similar adjacent pairs at the end (tail-anchored).

    Mirrors ``detect_response_loop`` logic but always returns the raw count
    regardless of ``min_repetitions``.  Window is capped at 10 responses.
    """
    if len(responses) < 2:
        return 0

    window = min(10, len(responses))
    recent = responses[-window:]
    normalized = [normalize_text(r) for r in recent]
    trailing = 0
    for i in range(len(normalized) - 2, -1, -1):
        n1, n2 = normalized[i], normalized[i + 1]
        if not n1 and not n2:
            sim = 1.0
        elif not n1 or not n2:
            sim = 0.0
        else:
            sim = text_similarity(recent[i], recent[i + 1])

        if sim >= similarity_threshold:
            trailing += 1
        else:
            break
    return trailing


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------


def get_default_db_path() -> str:
    """Resolve the default Hermes state.db path."""
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        return os.path.join(hermes_home, "state.db")
    return os.path.expanduser("~/.hermes/state.db")


def open_db(path: str) -> sqlite3.Connection:
    """Open state.db in read-only mode with URI and verify schema."""
    if not os.path.isfile(path):
        print(f"Error: database not found at {path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Verify schema
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cur.fetchall()}
    required = {"messages", "sessions"}
    missing = required - tables
    if missing:
        print(f"Error: DB missing required tables: {missing}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    return conn


def get_assistant_messages(
    conn: sqlite3.Connection, session_id: str
) -> list[sqlite3.Row]:
    """Return all assistant messages with non-empty content for a session."""
    cur = conn.execute(
        """SELECT id, content, timestamp FROM messages
           WHERE session_id = ? AND role = 'assistant'
             AND content IS NOT NULL AND content != ''
           ORDER BY id""",
        (session_id,),
    )
    return cur.fetchall()


def get_session_count(
    conn: sqlite3.Connection,
) -> int:
    """Return the total number of sessions in the DB."""
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM sessions")
    return cur.fetchone()["cnt"]


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def compute_similarity_stats(
    contents: list[str],
) -> dict[str, Any]:
    """Compute adjacent-pair similarity statistics for a list of response texts."""
    n = len(contents)
    if n < 2:
        return {
            "n": n,
            "pairs": 0,
            "ratios": [],
            "median": None,
            "mean": None,
            "max": None,
            "ge85": 0,
            "ge90": 0,
            "ge95": 0,
        }

    ratios: list[float] = []
    for i in range(1, len(contents)):
        r = text_similarity(contents[i - 1], contents[i])
        ratios.append(r)

    return {
        "n": n,
        "pairs": len(ratios),
        "ratios": ratios,
        "median": round(statistics.median(ratios), 4) if ratios else None,
        "mean": round(statistics.mean(ratios), 4) if ratios else None,
        "max": round(max(ratios), 4) if ratios else None,
        "ge85": sum(1 for r in ratios if r >= 0.85),
        "ge90": sum(1 for r in ratios if r >= 0.90),
        "ge95": sum(1 for r in ratios if r >= 0.95),
    }


def truncate_text(text: str, max_len: int = 60) -> str:
    """Truncate text for privacy-safe display."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# ---------------------------------------------------------------------------
# Subcommand: list-sessions
# ---------------------------------------------------------------------------


def cmd_list_sessions(args: argparse.Namespace) -> None:
    """List sessions with most assistant messages."""
    conn = open_db(args.db)

    cur = conn.execute(
        """SELECT s.id, s.title, s.source, s.started_at,
                  COUNT(m.id) AS assistant_count
           FROM sessions s
           LEFT JOIN messages m ON m.session_id = s.id
               AND m.role = 'assistant'
               AND m.content IS NOT NULL AND m.content != ''
           GROUP BY s.id
           ORDER BY assistant_count DESC
           LIMIT ?""",
        (args.limit,),
    )
    rows = cur.fetchall()

    if not rows:
        print("No sessions found.")
        conn.close()
        return

    total = get_session_count(conn)
    print(f"Total sessions in DB: {total}")
    print(f"Top {len(rows)} sessions by assistant message count:\n")
    print(f"  {'SESSION ID':35s} {'TITLE':40s} {'SOURCE':10s} {'ASSISTANT':>10s}")
    print("  " + "-" * 97)
    for row in rows:
        title = (row["title"] or "")[:38]
        print(
            f"  {row['id']:35s} {title:40s} {str(row['source'] or ''):10s}"
            f" {row['assistant_count']:10d}"
        )

    conn.close()


# ---------------------------------------------------------------------------
# Subcommand: extract
# ---------------------------------------------------------------------------


def cmd_extract(args: argparse.Namespace) -> None:
    """Extract and print adjacent-pair similarity stats for a session."""
    conn = open_db(args.db)

    rows = get_assistant_messages(conn, args.session_id)
    if not rows:
        print(
            f"No assistant messages with content found for session: {args.session_id}"
        )
        conn.close()
        return

    contents = [r["content"] for r in rows]
    stats = compute_similarity_stats(contents)

    print(f"Session ID: {args.session_id}")
    print(f"Total assistant messages (with content): {stats['n']}")
    print(f"Adjacent pairs analyzed: {stats['pairs']}")
    print(f"Median similarity: {stats['median']}")
    print(f"Mean similarity:   {stats['mean']}")
    print(f"Max similarity:    {stats['max']}")
    print(f"Pairs >= 0.85:     {stats['ge85']}")
    print(f"Pairs >= 0.90:     {stats['ge90']}")
    print(f"Pairs >= 0.95:     {stats['ge95']}")

    # Trailing-run lengths at various thresholds
    for thresh in (0.85, 0.90, 0.95):
        tr = trailing_run_length(contents, similarity_threshold=thresh)
        print(f"Trailing run >= {thresh}: {tr}")

    # Detection result at SPEC defaults
    detect_at = detect_response_loop(contents)
    if detect_at is not None:
        print(
            f"\nLoop DETECTED (tail-anchored, 0.95/3): run starts at index {detect_at}"
        )
    else:
        print("\nNo loop detected (tail-anchored, 0.95/3)")

    # Show sample of highest-similarity pair (privacy-safe)
    if stats["pairs"] > 0:
        max_ratio = -1.0
        max_idx = 0
        for i, r in enumerate(stats["ratios"]):
            if r > max_ratio:
                max_ratio = r
                max_idx = i

        if max_ratio >= 0.90:
            print(f"\nMost similar pair (idx {max_idx}, ratio={max_ratio:.4f}):")
            print(f"  A: {truncate_text(contents[max_idx], 60)}")
            print(f"  B: {truncate_text(contents[max_idx + 1], 60)}")

    conn.close()


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> None:
    """Run tail-anchored detection across ALL sessions for threshold recalibration."""
    conn = open_db(args.db)

    threshold = args.threshold
    min_rep = args.min_repetitions

    total_sessions = get_session_count(conn)

    # Find all sessions with at least 2 assistant responses
    cur = conn.execute(
        """SELECT s.id, COUNT(m.id) AS cnt
           FROM sessions s
           JOIN messages m ON m.session_id = s.id
               AND m.role = 'assistant'
               AND m.content IS NOT NULL AND m.content != ''
           GROUP BY s.id
           HAVING cnt >= 2
           ORDER BY cnt DESC"""
    )
    candidate_rows = cur.fetchall()

    print(f"Total sessions in DB: {total_sessions}")
    print(f"Sessions with >= 2 assistant messages: {len(candidate_rows)}")
    print(f"Threshold: {threshold}, min_repetitions: {min_rep}")
    print()

    # Per-session results
    triggered: list[dict[str, Any]] = []
    trailing_runs: list[int] = []
    not_triggered_count = 0

    for row in candidate_rows:
        sid = row["id"]
        msgs = get_assistant_messages(conn, sid)
        contents = [r["content"] for r in msgs]

        # Raw trailing-run length
        tr = trailing_run_length(contents, similarity_threshold=threshold)
        trailing_runs.append(tr)

        # Detection
        detect_at = detect_response_loop(
            contents,
            similarity_threshold=threshold,
            min_repetitions=min_rep,
            window_size=10,
        )

        if detect_at is not None:
            triggered.append(
                {
                    "session_id": sid,
                    "n": len(contents),
                    "trailing_run": tr,
                    "run_start": detect_at,
                    "tail_ratio": round(tr / max(len(contents), 1), 4),
                }
            )
        else:
            not_triggered_count += 1

    # Summary
    print(f"Triggered: {len(triggered)} / {len(candidate_rows)}")
    print(f"Not triggered: {not_triggered_count}")
    print()

    if trailing_runs:
        print(f"Trailing-run distribution (threshold={threshold}):")
        # Bin trailing runs
        max_run = max(trailing_runs)
        for length in range(0, max_run + 1):
            count = trailing_runs.count(length)
            if count > 0:
                bar = "#" * min(count, 60)
                print(f"  {length:3d}: {count:5d}  {bar}")
        print()

    if triggered:
        print("Triggered sessions:")
        print(
            f"  {'SESSION ID':35s} {'#MSGS':>6s} {'TRAIL':>5s} {'START':>5s}"
            f" {'TAIL_RATIO':>10s}"
        )
        print("  " + "-" * 63)
        for t in triggered[:50]:  # cap display at 50
            print(
                f"  {t['session_id']:35s} {t['n']:6d} {t['trailing_run']:5d}"
                f" {t['run_start']:5d} {t['tail_ratio']:10.4f}"
            )
        if len(triggered) > 50:
            print(f"  ... and {len(triggered) - 50} more")

    # Histogram of trailing runs at key min_repetition thresholds
    print()
    print("What-if analysis (different min_repetitions):")
    for m in [2, 3, 4, 5]:
        triggered_m = sum(1 for t in trailing_runs if t >= m)
        pct = triggered_m / max(len(candidate_rows), 1) * 100
        print(
            f"  min_reps={m}: {triggered_m}/{len(candidate_rows)}"
            f" ({pct:.1f}%) would trigger"
        )

    conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Read-only analysis of response-loop data from Hermes session DB.",
    )
    parser.add_argument(
        "--db",
        default=get_default_db_path(),
        help=f"Path to state.db (default: {get_default_db_path()})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-sessions
    ls_parser = subparsers.add_parser(
        "list-sessions", help="List sessions with most assistant messages"
    )
    ls_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max sessions to list (default: 10)",
    )

    # extract
    ext_parser = subparsers.add_parser(
        "extract", help="Extract similarity stats for a session"
    )
    ext_parser.add_argument("--session-id", required=True, help="Session ID to analyze")

    # validate
    val_parser = subparsers.add_parser(
        "validate",
        help="Run tail-anchored detection across all sessions for threshold recalibration",
    )
    val_parser.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        help="Similarity threshold (default: 0.95)",
    )
    val_parser.add_argument(
        "--min-repetitions",
        type=int,
        default=3,
        help="Min consecutive similar pairs to trigger (default: 3)",
    )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    if args.command == "list-sessions":
        cmd_list_sessions(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
