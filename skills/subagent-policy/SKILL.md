---
name: subagent-policy
description: "Defines the usage policy, invocation patterns, constraints, and best practices for subagents (delegate_task). Covers role separation and implementation patterns, centered on SOUL.md."
version: 1.1.0
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

> The "current value" above is based on the current `~/.hermes/config.yaml` settings.

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

The following tools are automatically removed from leaf subagents (`role="leaf"`):

| Blocked tool | Reason |
| ------------ | ------ |
| `delegate_task` | Prevent recursive delegation |
| `clarify` | No user interaction from subagents |
| `memory` | No writes to shared memory |
| `send_message` | No cross-platform side effects |
| `execute_code` | Children should reason step-by-step |

Orchestrators (`role="orchestrator"`) retain only `delegate_task` as an exception from the blocked list above; the rest (`clarify` / `memory` / `send_message` / `execute_code`) are removed just like leaf subagents.
Standard tools such as file and terminal are available the same as for leaf subagents.
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

| Item | Parent | Child (subagent) | Mitigation |
| ---- | ------ | ----------------- | ---------- |
| SOUL.md | Loaded | Not loaded | Pass critical rules via the `context` parameter |
| Memory | Enabled | `skip_memory=True` | Pass information via the `context` parameter |
| Context files | Loaded | `skip_context_files=True` | Pass information via the `context` parameter |
| Plugin hooks | Fire | Do not fire | Keep hook logic self-contained in the parent |
| Fallback provider | Enabled | Not inherited | Configure on the proxy side |

---

## 5. Best Practices

### 5.1. Using the `context` Parameter

Use the `context` parameter to pass critical behavioral rules to subagents.

```python
delegate_task(
    goal="Perform a code review",
    context=(
        "CRITICAL RULES (must follow):\n"
        "- Main agent's role is planning only; ALL execution delegated to subagents.\n"
        "- Subagent instructions MUST be written in English.\n"
        "- For coding tasks: read opencode skill first, then run opencode CLI inside delegate_task.\n"
        "- NEVER run opencode directly; always inside a subagent.\n"
        "- Before presenting changes: run CI checks AND opencode review.\n"
        "- Use ghq for cloning. Never commit to main.\n"
        "- nix-first: check flake.nix before raw commands.\n"
        "\n"
        "ORIGINAL TASK CONTEXT:\n"
        "[... actual task context here ...]"
    )
)
```

> **Note:** Because `context` is placed in the middle of the system prompt, it can degrade due to "lost in the middle" effects in long sessions. Keep critical rules concise and near the beginning.

### 5.2. Worktree and Branch Management

Subagents may create many temporary branches and worktrees.

**Preventive measures:**

- Instruct subagents to use a single branch-naming convention
- Create multiple branches only when parallelism is required

---

## 6. Related Skills

| Skill | Role |
| ----- | ---- |
| `hermes-agent` | Hermes Agent configuration, extension, and usage |
| `git-workflow` | ghq + worktree mode, branch management, PR conventions |
| `specification-authoring` | Spec authoring, auditing, and review |
| `opencode` | Code review and implementation via the OpenCode CLI |
