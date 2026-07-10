---
name: subagent-policy
description: "Delegation policy for subagents (delegate_task). Covers role separation, direct-vs-delegate criteria, decomposition sequencing, inheritance, and verification boundaries."
version: 2.0.0
author: yaYoi
license: MIT
metadata:
  hermes:
    tags: [subagent, delegate_task, policy, hermes-agent]
    related_skills: [hermes-agent, git-workflow, specification-authoring, opencode]
---

# Subagent Operation Policy

## 1. Role Model / Outcome Ownership

There are three distinct actors. The user gives intent to the main agent (PM). The PM owns outcome delivery and may delegate work to subagents.

| Actor | Role | Scope |
| ------- | ------ | ------- |
| **User** | Principal | States goals, provides requirements, reviews results |
| **Main agent (PM)** | Project manager, architect, integrator | Intent capture, planning, decomposition, delegation decisions, synthesis, final judgment, verification, user communication |
| **Subagent** | Worker, researcher, orchestrator | Executes delegated tasks within bounded scope; returns distilled results |

The PM is accountable for end-to-end correctness. Subagents are accountable for the task they were given.

## 2. Use the Right Actor (Direct vs. Delegate)

Do not default to "always delegate" or "always execute directly". Choose the right actor for each unit of work.

### Direct PM execution is correct when the work is

- **PM-owned by nature** — planning, analysis, synthesis, verification, user-facing communication, final judgment calls, integration of subagent results.
- **Trivial and bounded** — a single known-replacement edit, a short deterministic command whose output is predictable and small.
- **Concrete PM-authored text** — writing prose, comments, or configuration that the PM already knows the exact content of.
- **Bounded programmatic orchestration** — tool chains where intermediate tool results are processed and filtered into a compact result for the next step.

### Delegate to a subagent when work is

- **Coding** — implementation, refactoring, code review, test generation, multi-file changes.
- **Exploratory** — research, debugging, root-cause analysis, output-unpredictable commands (unknown file sizes, compilation logs, CI status).
- **Long or output-unpredictable** — any task whose result length or shape cannot be bounded in advance.
- **Parallelizable** — independent workstreams that should run concurrently.
- **Worker-style** — mechanical execution better isolated from PM context.

When uncertain, assess on cost-benefit: delegation filters noisy output and protects PM context budget, but adds a fixed overhead per call. If the task is small and deterministic, direct execution is cheaper.

No hardcoded "always delegate" rule. Evaluate per task.

## 3. Delegation Decomposition and Sequencing

Split work into the smallest single-responsibility unit that a subagent can complete without confusion.

- **Independent tasks** — dispatch in a single parallel batch via `delegate_task(tasks=[...])`. The `role="orchestrator"` setting is separate and only means the child may delegate further.
- **Dependent tasks** — sequence by feeding each subagent's output into the next via the `context` parameter.
- **Waiting tasks** (CI polling, reviews) — never bundle with editing work. Dispatch as separate delegation once the trigger completes.
- **PM's step decomposition** — each step in the PM's plan (branch, edit, commit, push, CI, merge) is a separate delegation target, provided it qualifies under section 2. Do not hand a multi-step plan to one subagent just because it is clearly written.
- **Context budget** — delegate noisy or output-heavy work to protect PM context budget.

## 4. Delegation Contract

Every `delegate_task` call must specify:

1. **Goal** — what the subagent must accomplish (the `goal` parameter).
2. **Context** — critical behavioral rules and task background (the `context` parameter). Subagents do not inherit SOUL.md, memory, or project context files, so pass everything task-relevant explicitly.
3. **Constraints** — tool restrictions, budget limits, boundaries (what is in scope and what is not).
4. **Required evidence** — citations, file paths, test results the subagent must return.
5. **Success criteria** — how the PM will decide the task is done.
6. **Output format** — the shape of the expected result (summary, structured JSON, diff, list).

Template:

```python
delegate_task(
    goal="...",
    context=(
        "TASK RULES:\n"
        "- [critical behavioral rules]\n"
        "- [prohibitions: no --admin, no API bypass]\n"
        "\n"
        "BACKGROUND:\n"
        "[task context the subagent needs]"
    ),
)
```

## 5. Inheritance and Tool Limits

| Item | Parent (PM) | Child (subagent) |
| ------ | ------------- | ------------------ |
| SOUL.md | Loaded | Not loaded |
| Memory | Enabled | Disabled |
| Project context files | Loaded | Not loaded |
| Plugin hooks | Fire | Do not fire |
| Fallback chain | Enabled | Inherited |

Subagents inherit the parent's available toolsets, with blocked tools removed according to role.

### Blocked tools

| Tool | Leaf | Orchestrator |
| ------ | ------ | ------------- |
| `delegate_task` | Blocked | Allowed |
| `clarify` | Blocked | Blocked |
| `memory` | Blocked | Blocked |
| `send_message` | Blocked | Blocked |
| `execute_code` | Blocked | Blocked |

### Concurrency limits

Concurrency settings (max children, depth) are live config values. Inspect current Hermes configuration when limits matter; do not hardcode.

## 6. Verification and Protection Boundaries

- **Parent verifies external side effects.** Before reporting success, the PM must independently verify that any external-write delegation (push, PR, merge, deploy) produced the intended outcome. Do not trust the subagent's self-report alone.
- **Protection bypass is failure.** If a subagent reports that it bypassed a protection (`--admin`, API merge, ruleset weakening) to achieve the goal, treat it as a failure regardless of outcome. The subagent should stop and report the block instead.
- **Review gates.** Run code review after subagent implementation completes, before presenting changes to the user, and before pushing a changeset intended for PR. CI gates must pass before requesting user review or merging.
- **Large review splitting.** Split reviews by file or component when single-pass timeouts occur. Fall back to read-only `delegate_task` subagents only when the coding agent consistently times out after splitting.

## 7. Related Skills

| Skill | Role |
| ------- | ------ |
| `hermes-agent` | Hermes Agent configuration, extension, and usage |
| `git-workflow` | ghq + worktree mode, branch management, PR conventions |
| `specification-authoring` | Spec authoring, auditing, and review |
| `opencode` | Code review and implementation via OpenCode CLI |
