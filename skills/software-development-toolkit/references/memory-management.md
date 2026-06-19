---
name: memory-management
description: "Rules for saving and managing persistent memory across sessions. Load when deciding what to save to MEMORY.md or USER.md."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [memory, persistence, user-preferences, conventions]
    related_skills: [host-environment]
---

# Memory Management Rules

## Overview

You have persistent memory across sessions. This skill defines what to save, where to save it, and how to write it.

## What to Save

### ✅ Save (Durable Facts)
- User preferences
- Environment details
- Tool quirks
- Stable conventions

**Priority:** Save what reduces future user steering — the most valuable memory prevents the user from having to correct or remind you again.

### ❌ Do NOT Save
- Task progress
- Session outcomes
- Completed-work logs
- Temporary TODO state

**Alternative:** Use `session_search` to recall those from past transcripts.

## Writing Style

Write memories as **declarative facts**, not instructions to yourself.

| ✅ Good | ❌ Bad |
|--------|--------|
| "User prefers concise responses" | "Always respond concisely" |
| "Project uses pytest with xdist" | "Run tests with pytest -n 4" |

## Location Discipline

| Type | Destination |
|------|-------------|
| Project-specific conventions | Work repo's `AGENTS.md` or `.cursorrules` |
| Reusable workflows / problem solutions | Skills via `skill_manage` |
| Stable cross-project preferences only | Global memory (`MEMORY.md` / `USER.md`) |

## Volatile Specifics

Do NOT save volatile specifics such as exact model names, versions, or URLs to global memory unless they are long-lived infrastructure defaults.

## Special Cases

### User Interpretation Clarifications
When the user corrects your understanding of a rule, policy, or their intent, save that clarification as a declarative fact so future sessions inherit the correct interpretation without requiring the user to re-explain. This is part of "user preferences" and should be saved proactively.

### Environment Facts
Facts about how Hermes should operate — including memory's own purpose, delegation behavior, or tool usage patterns — are environment facts about Hermes itself and may be saved in memory when they are stable and reduce future user steering.

**Note:** Procedural rules still belong in skills or `SOUL.md`; this exception is for declarative facts about Hermes's operational environment.

## Session Search Best Practices

When the user asks you to search past conversations (e.g., 「過去の会話を探索して下さい」「前のセッションの続き」):

1. **Start broad, then narrow.** Use wide keyword queries first (e.g., `profile directory structure`, `settings.toml profiles`). If results are insufficient, try related terms rather than repeating the same query.
2. **Follow the trail.** When a session looks relevant, use `session_search(session_id=..., around_message_id=...)` to scroll forward/backward and find the exact decision point.
3. **Do NOT give up early.** The user expects autonomous investigation. Asking "which session?" or "what was decided?" after they already told you to search frustrates them — especially when they said 「前のセッションの続き」.
4. **When stuck, vary queries.** Try: topic keywords, file names, decision phrases (「決定」「確定」「grill-me」), or structural terms (「ディレクトリ」「構造」「tree」).
5. **Report what you found honestly.** If you cannot locate the specific conversation after thorough search, state that clearly rather than fabricating or asking the user to repeat themselves.

## Maintenance

- Deduplicate proactively
- Refactor when stale
