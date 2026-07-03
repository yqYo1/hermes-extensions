---
name: subagent-policy
description: "Defines the usage policy, invocation patterns, constraints, and best practices for subagents (delegate_task). Covers role separation and implementation patterns, centered on SOUL.md."
version: 1.3.0
author: yaYoi
license: MIT
metadata:
  hermes:
    tags: [subagent, delegate_task, policy, best-practices, hermes-agent]
    related_skills: [hermes-agent, git-workflow, specification-authoring]
---

# Subagent Operation Policy

## 1. Core Principles

### 1.1. Delegate First, Execute Never

The main agent (PM) only performs planning, decomposition, delegation decisions, result integration, and user communication.

| Role | Actor | Responsibility |
| ---- | ------ | -------------- |
| **PM** | Main agent | Task analysis, decomposition, delegation decisions, result integration, user communication |
| **Programmer** | OpenCode / coding subagent | All code work (implementation, refactoring, review, tests) |
| **PL/Researcher** | Subagent (delegate_task) | Research, analysis, information gathering |
| **Worker** | Subagent (delegate_task, leaf) | Single-step mechanical tasks, file operations, command execution |

### 1.2. Boundary Between Delegation and Direct Execution

| Delegate (always to subagents) | Direct execution allowed (main agent) |
| ------------------------------ | ------------------------------------- |
| All coding | Analysis, planning |
| All research and investigation | Integration, communication |
| All mechanical execution | Trivial lookups (a single tool call) |

> **When in doubt, delegate.**

---

## 2. Subagent Configuration

### 2.1. Concurrency Settings

| Setting | Current value | Description |
| ------- | ------------- | ----------- |
| `max_concurrent_children` | 12 | Max subagents the PM can spawn in one synchronous batch. This is the upper bound for task splitting. |
| `max_async_children` | 3 | Max concurrent background (background=true) subagents. Excess is rejected (no queuing) |
| `max_spawn_depth` | 2 | Delegation tree depth cap. 1=flat, 2+=nested orchestration |
| `orchestrator_enabled` | true | Enables `role="orchestrator"` |
| `inherit_mcp_toolsets` | true | Whether MCP toolsets are inherited by children |

---

## 3. Using Subagents

### 3.1. Basic Invocation

```python
delegate_task(
    goal="Description of the investigation task",
    context="Required background information and constraints",
)
```

### 3.2. Toolsets

The `toolsets` parameter cannot be specified; it is rejected at runtime. Always omit it. Subagents inherit the parent's full toolset, including skills.

### 3.3. Blocked Tools

The following tools are not available to subagents:

| Blocked tool | leaf | orchestrator |
| ------------ | ---- | ------------ |
| `delegate_task` | ❌ | ✅ |
| `clarify` | ❌ | ❌ |
| `memory` | ❌ | ❌ |
| `send_message` | ❌ | ❌ |
| `execute_code` | ❌ | ❌ |

Nesting depth is bounded by `max_spawn_depth`.

### 3.4. Choosing Between Orchestrator and Leaf

| Role | Use case | Nesting |
| ---- | -------- | ------- |
| `leaf` (default) | Single-task execution | No further delegation |
| `orchestrator` | Coordinating multiple tasks, parallel execution | Can spawn further children |

```python
# Orchestrator example
delegate_task(
    goal="Modify multiple files in parallel",
    role="orchestrator",
    tasks=[
        {"goal": "Modify file A"},
        {"goal": "Modify file B"},
    ]
)
```

---

## 4. Subagent Constraints

### 4.1. What Is Not Inherited

| Item | Parent | Child (subagent) |
| ---- | ------ | ----------------- |
| SOUL.md | Loaded | Not loaded |
| Memory | Enabled | Disabled |
| Context files | Loaded | Not loaded |
| Plugin hooks | Fire | Do not fire |
| Fallback provider | Enabled | Not inherited |

Pass critical rules and information to the child via the `context` parameter.

---

## 5. Best Practices

### 5.1. Using the `context` Parameter

Use the `context` parameter to pass critical behavioral rules and task background to subagents.

```python
delegate_task(
    goal="Perform a code review",
    context=(
        "CRITICAL RULES (must follow):\n"
        "- [project-specific rules the subagent must obey]\n"
        "\n"
        "ORIGINAL TASK CONTEXT:\n"
        "[... actual task context here ...]"
    )
)
```

### 5.2. Worktree and Branch Management

Subagents may create many temporary branches and worktrees.

**Preventive measures:**

- Instruct subagents to use a single branch-naming convention
- Create multiple branches only when parallelism is required

### Delegation Criteria and Execution Strategy

**The delegation criterion is output unpredictability or predictably-long output — not command count.**
Delegate when a command's output length cannot be bounded in advance, OR when the output is predictable but long.
The former: file/log reads whose location or size is unknown, compiles/installs whose progress or error output grows, any command whose worst-case output is unknown.
The latter: CI status watches, verbose logs.
Direct-execute only when the output is BOTH predictable AND short (basic git add/commit/push/diff/status — except long-output ones like `log`, simple text patches with a known replacement, writing PM-authored concrete content to a file).

**File edits: judge by exploration need, not by the action type.**
PM-authored concrete draft written to file = direct (output is known and short).
Edits that require exploration, trial-and-error, or ripple analysis across files = delegate (the exploration makes the output unpredictable).

**Split until each unit is a single simple task.**
A unit is at its maximum when (1) the subagent can complete it without confusion, AND (2) no part of it could run in parallel.
If either condition fails, split further.
Adjust granularity based on prompt quality and the specific subagent model — when a delegation underperforms, retry with finer splitting; when a coarse bundle works, coarsen next time.
Command count is only a secondary signal, not the splitting unit.

- **Independent tasks → parallel batch.** When sub-tasks have no data dependency, dispatch them in a single `delegate_task` call (or concurrent calls) so they run in parallel.
- **Dependent tasks → sequential chain.** When task B needs task A's output, run A first, then feed its result into B via the `context` parameter. Do not bundle them into one subagent.
- **PM owns analysis and integration.** Reading results, cross-referencing, drawing conclusions, and planning next steps are PM responsibilities. Delegate data gathering and mechanical execution; do the synthesis yourself.

**Splitting pattern (investigation example).** "Investigate and compare A, B, C" should split into: investigate A, investigate B, investigate C (parallel), then re-investigate gaps found in each (0-3 sequential
follow-ups). If A is composite, first enumerate what's in A, then split into one sub-task per feature.

**PM's own step splits are execution units, not explanation structure.** When PM decomposes a task into steps (e.g. "branch → edit → commit → push → PR → CI → merge"), each step is a separate delegation target —
provided that step qualifies for delegation under the output-unpredictability criterion above.
Do not hand a multi-step plan to one subagent just because the plan is clearly written — the writing is for PM's own clarity, and the steps become execution units that go to separate subagents.
A subagent that "follows steps 1-8" is a sign the task was not actually split.

**Waiting tasks are separate units.** CI status checks, review polling, and other wait-for-external tasks are never bundled with edit/commit work.
Dispatch them as their own delegation once the triggering push completes, so the editing subagent's lifecycle ends at its own boundary.

**Cost rationale.** Subagents filter raw output and report only the relevant result, keeping the PM's context lean and cost predictable.
PM execution may start cheaper, but unfiltered output causes sharp cost spikes; delegation trades a small fixed overhead for a gentler, more predictable cost curve.

---

## 6. Related Skills

| Skill | Role |
| ----- | ---- |
| `hermes-agent` | Hermes Agent configuration, extension, and usage |
| `git-workflow` | ghq + worktree mode, branch management, PR conventions |
| `specification-authoring` | Spec authoring, auditing, and review |
| `opencode` | Code review and implementation via the OpenCode CLI |
