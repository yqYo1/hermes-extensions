---
name: subagent-driven-development
description: "Execute implementation plans via delegate_task subagents with systematic two-stage review (spec compliance + code quality)."
version: 1.1.0
author: yqYo1 (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [delegation, subagent, implementation, workflow, parallel, review]
    related_skills: [subagent-operation-policy, software-development-toolkit, specification-authoring]
---

# Subagent-Driven Development

## Overview

Execute implementation plans by dispatching fresh subagents per task with systematic
two-stage review: **spec compliance** first, then **code quality**.

**Core principle:** Fresh subagent per task + two-stage review = high quality, fast iteration.

## When to Use

Use this skill when you have an implementation plan and tasks are mostly independent.
The default policy is to use `delegate_task` for any task that can be delegated.

**Key rules:**
- Always use `delegate_task` unless genuinely unavailable
- Subagent instructions MUST be written in English
- Always include `"skills"` in toolsets (or omit to inherit)
- Parallel execution by default for independent tasks
- Maximum 5 parallel children per delegate_task call

## Two-Stage Review

| Review Type | Performer | When |
|-------------|-----------|------|
| Spec compliance | Subagent reviewer | After implementer completes |
| Code quality | Subagent reviewer | After spec compliance passes |
| Final integration | **Main agent** (direct) | Before push/user presentation |

## Per-Task Workflow

1. **Dispatch implementer subagent** with full task context
2. **Dispatch spec compliance reviewer** — verifies against original spec
3. **Dispatch code quality reviewer** — checks style, errors, security
4. **Fix issues** if review fails, then re-review
5. **Mark complete** and move to next task

## Task Granularity

| Dimension | Limit |
|-----------|-------|
| Scope | 1 concern (1 function / 1 file / 1 endpoint) |
| Code size | ≤50 lines new code (tests excluded) |
| Files touched | ≤3 files |
| Execution time | ≤10 minutes subagent runtime |

## Critical Rules

- **Never skip reviews** — both spec compliance AND code quality
- **Spec review before quality review** — wrong order causes rework
- **Same-file tasks MUST be sequential** — parallel only for disjoint files
- **Verify subagent claims** — always check file existence, test output, git status
- **Final integration review by main agent** — never delegate this

## Common Pitfalls

- Letting implementer self-review replace actual review
- Skipping scene-setting context for subagents
- Making subagents read plan files (provide full text in context instead)
- Ignoring subagent questions (answer before letting them proceed)
- Accepting "close enough" on spec compliance

## Full Reference

For complete details including:
- Subagent timeout handling
- Branch discipline for subagents
- Context budget management
- Pre-commit verification pipeline
- Parallel execution patterns
- False implementation report prevention

See: `references/subagent-driven-development.md` in the `software-development-toolkit` skill.
