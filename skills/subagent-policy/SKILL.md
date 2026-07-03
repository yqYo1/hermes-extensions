---
name: subagent-policy
description: "Defines the usage policy, invocation patterns, constraints, and best practices for subagents (delegate_task). Covers role separation and implementation patterns, centered on SOUL.md."
version: 1.2.0
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

### Task Sizing and Execution Strategy

**Keep each delegated unit small (a few commands).** Subagents match PM ability on mechanical tasks but degrade as complexity rises. Prefer many small delegations over one large one.

- **Independent tasks → parallel batch.** When sub-tasks have no data dependency, dispatch them in a single `delegate_task` call (or concurrent calls) so they run in parallel.
- **Dependent tasks → sequential chain.** When task B needs task A's output, run A first, then feed its result into B via the `context` parameter. Do not bundle them into one subagent.
- **PM owns analysis and integration.** Reading results, cross-referencing, drawing conclusions, and planning next steps are PM responsibilities. Delegate data gathering and mechanical execution; do the synthesis yourself.

Even a handful of commands is worth delegating rather than executing directly — the result returns to PM for integration.

---

## 6. Related Skills

| Skill | Role |
| ----- | ---- |
| `hermes-agent` | Hermes Agent configuration, extension, and usage |
| `git-workflow` | ghq + worktree mode, branch management, PR conventions |
| `specification-authoring` | Spec authoring, auditing, and review |
| `opencode` | Code review and implementation via the OpenCode CLI |
