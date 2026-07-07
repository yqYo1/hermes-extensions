---
name: subagent-policy
description: "Defines the usage policy, invocation patterns, constraints, and best practices for subagents (delegate_task). Covers role separation, delegation criteria, failure modes, and implementation patterns."
version: 1.5.0
author: yaYoi
license: MIT
metadata:
  hermes:
    tags: [subagent, delegate_task, policy, best-practices, hermes-agent]
    related_skills: [hermes-agent, git-workflow, specification-authoring, opencode]
---

# Subagent Operation Policy

## 1. Core Principles

### 1.1. Delegate First, Execute Never

The main agent (PM) only performs planning, decomposition, delegation decisions, result integration, and user communication.

| Role | Actor | Responsibility | Typical `role` param |
| ---- | ------ | -------------- | ------------------- |
| **PM** | Main agent | Task analysis, decomposition, delegation decisions, result integration (synthesis, not aggregation), user communication | — (PM itself) |
| **Programmer** | OpenCode CLI or coding subagent | All code work (implementation, refactoring, review, tests) | `leaf` for single-file, `orchestrator` for multi-file parallel |
| **PL/Researcher** | Subagent (delegate_task) | Research, analysis, information gathering, investigation | `leaf` for single-thread investigation, `orchestrator` for parallel multi-source |
| **Worker** | Subagent (delegate_task, `leaf`) | Single-step mechanical tasks, file operations, command execution | `leaf` (always) |

### 1.2. Boundary Between Delegation and Direct Execution

| Delegate (always to subagents) | Direct execution allowed (main agent) |
| ------------------------------ | ------------------------------------- |
| All coding | Analysis, planning |
| All research and investigation | Integration, communication |
| All mechanical execution | Trivial lookups (a single tool call) |

> **When in doubt, delegate.**
>
> **Hard rule:** Do NOT edit files directly from the main agent when a subagent or coding agent
> could handle it. Direct main-agent editing is a last resort, not a default. If you find yourself
> writing patch blocks or file edits directly, pause and ask whether a subagent could have done
> this instead. Maximize appropriate delegation to subagents and coding agents.

---

## 2. Subagent Configuration

### 2.1. Concurrency Settings

| Setting | Current value | Description |
| ------- | ------------- | ----------- |
| `max_concurrent_children` | 12 | Max subagents that can run concurrently in one synchronous batch. This caps concurrency, NOT the splitting unit — split by task simplicity (§5.3), then run up to 12 in parallel; queue the rest. |
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

### 5.3. Delegation Criteria and Execution Strategy

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
- **PM owns analysis and integration.** Reading results, cross-referencing, drawing conclusions, and planning next steps are PM responsibilities.
Synthesis is not aggregation — evaluate each subagent's reliability, identify contradictions/gaps, and produce an integrated judgment.
Delegate data gathering and mechanical execution; do the synthesis yourself.

**Splitting pattern (investigation example).** "Investigate and compare A, B, C" should split into: investigate A, investigate B, investigate C (parallel), then re-investigate gaps found in each (0-3 sequential
follow-ups). If A is composite, first enumerate what's in A, then split into one sub-task per feature.

**PM's own step splits are execution units, not explanation structure.** When PM decomposes a task into steps (e.g. "branch → edit → commit → push → PR → CI → merge"), each step is a separate delegation target —
provided that step qualifies for delegation under the output-unpredictability criterion above.
Do not hand a multi-step plan to one subagent just because the plan is clearly written — the writing is for PM's own clarity, and the steps become execution units that go to separate subagents.
A subagent that "follows steps 1-8" is a sign the task was not actually split.

**Waiting tasks are separate units.** CI status checks, review polling, and other wait-for-external tasks are never bundled with edit/commit work.
Dispatch them as their own delegation once the triggering push completes, so the editing subagent's lifecycle ends at its own boundary.

**Context budget threshold.** When the PM's context utilization exceeds roughly 40-60%, reasoning quality degrades.
Delegation is the primary mechanism to prevent this — noisy operations (search, code analysis, verbose tool output) run in subagents, and only distilled results return to the PM.

**Cost rationale.** Subagents filter raw output and report only the relevant result, keeping the PM's context lean and cost predictable.
PM execution may start cheaper, but unfiltered output causes sharp cost spikes; delegation trades a small fixed overhead for a gentler, more predictable cost curve.

### 5.4. Input/Output Contracts

A well-formed delegation specifies four elements explicitly:

1. **Purpose** — what the subagent must accomplish (the `goal`).
2. **Output format** — the shape of the expected result (prose summary, structured JSON, single value, diff).
3. **Tool guidance** — which tools are relevant; any constraints (e.g. "read-only", "do not commit").
4. **Task boundary** — what is in scope and what is NOT (prevents overlap and gaps).

The `context` parameter template in §5.1 covers rules and background; combine it with explicit output-format instructions to close the contract.
Strict output schemas also mitigate synthesis mismatch when parallel workers return contradictory results.

### 5.5. Failure Modes and Countermeasures

Subagents fail in characteristic ways. Recognize and pre-empt them:

- **Instruction drift / protection bypass** — the subagent "unblocks" itself by disabling rulesets, using `--admin`, or calling merge APIs directly.
  Countermeasure: state prohibitions in the prompt ("NEVER --admin or API bypass; if blocked, STOP and report"); reject any merge the standard command refused.
- **Cost spike (over-spawning)** — many workers spawned for a task a single agent could handle.
  Countermeasure: apply the delegation criterion (§5.3); cap worker count to what the task needs.
- **Premature termination** — worker stops at the first plausible result without thorough investigation.
  Countermeasure: instruct investigation depth explicitly; request evidence citations.
- **Synthesis mismatch** — parallel workers return contradictory results the PM cannot reconcile.
  Countermeasure: require strict output schemas; have PM evaluate per-worker reliability.
- **Context drift** — worker loses track of the original goal mid-task.
  Countermeasure: add checkpoints; keep `context` focused on critical rules.
- **Prompt injection** — untrusted input (web pages, file contents) hijacks worker behavior.
  Countermeasure: sanitize inputs; isolate dangerous tools; require human approval for high-risk actions.

**Hard rule:** when a subagent reports it bypassed a protection to achieve the goal, treat that as a failure — not a success — even if the end state looks correct.

### 5.6. Cost Optimization and Result Distillation

- **Distill before returning.** A subagent should return a distilled summary (target: tens to low-hundreds of lines), not raw 5,000-line output. The PM's context is the scarce resource.
- **Model tiering.** Use cheaper/faster models for mechanical leaf tasks; reserve the strong model for orchestration and synthesis. Subagents inherit the parent model by default — override per-delegation when the task is simple.
- **Token budget.** For expensive delegations, set expectations on output size (`max_tokens`, structured output constraints) to bound cost.
- **Caching and batching.** Cache repeated sub-agent results; batch independent tasks into one parallel dispatch instead of sequential calls.
- **Stop early.** Define early-stop conditions (e.g. "stop after finding the first verified root cause") to avoid unnecessary exploration.

### 5.7. Coding Agent Delegation

Coding agents (OpenCode, Claude Code, Codex, etc.) are specialized subagents for code work. The PM delegates coding work to them rather than performing code edits directly.

#### 5.7.1. When to Use Coding Agents

| Appropriate | Inappropriate |
| ----------- | ------------- |
| Implementation of new features | Quick deterministic edits (single known replacement) |
| Refactoring and restructuring | Non-code tasks better handled by worker/researcher subagents |
| Code review and PR review | Trivial one-line changes |
| Generating tests from code | Environment setup or config-only changes |
| Generating documentation from code | Read-only investigation of very small scope |
| Multi-file changes requiring ripple analysis | |

Apply the delegation criterion from §5.3: delegate when the output is unpredictable or predictably-long. Coding agents excel at tasks where the exploration surface is large — reading many files, identifying patterns, making cross-cutting changes.

#### 5.7.2. Model Selection

Do NOT force a specific model on a coding agent unless:

- The user explicitly requests a specific model
- The default model is clearly failing for the task type (e.g., a weak model for complex reasoning)
- Retrying after timeout or failure and a different model is a reasonable fallback

Otherwise, let the coding agent use its configured defaults. Overriding `--model` without cause may select a slower, more expensive, or less appropriate model.

#### 5.7.3. Review Timing Gates

Run code review at ALL of the following checkpoints:

1. **After each subagent completes implementation** — review what the subagent produced before integrating it into the main work.
2. **Before presenting changes to the user** — review the complete changeset before requesting user review.
3. **Before pushing a changeset intended for pull request or user review** — review the working branch before the push that culminates work for review. (Frequent intermediate pushes to share work-in-progress do not require a full review before each one.)
4. **At natural breakpoints** — when pausing work, switching phases, or completing a major milestone.

Additionally:

- Run CI checks (or equivalent gates) before requesting user review; never skip this step.
- Review and CI gates must both pass before opening or merging a PR.
- Never use `--admin` flags or API-based merge bypasses.
- Do not substitute subagent review for coding-agent review as a matter of routine — if the
  coding agent fails on a normal scope, retry with fallback model or split the review scope. The
  only exception is when the coding agent consistently times out even after splitting the review
  scope (see §5.7.4); in that specific case, fall back to a `delegate_task` subagent with read-only
  tools instead.

#### 5.7.4. Large Review Splitting

When a code review is expected to exceed the coding agent's bounded timeout:

1. Split the review by file, component, or concern area — not by directory glob.
2. Pass specific file paths rather than asking the agent to discover files.
3. Request a high-level summary first, then deep-dive specific areas in follow-up rounds.
4. If the coding agent consistently times out even after splitting, fall back to a `delegate_task` subagent with read-only tools for the review instead.

#### 5.7.5. Subagent Wrapper Pattern

Prefer running coding agents inside a `delegate_task` subagent rather than invoking them directly from the PM:

```python
delegate_task(
    goal="Use a coding agent to implement OAuth refresh flow and add tests",
    context=(
        "CRITICAL RULES:\n"
        "- Run the coding agent in the project directory\n"
        "- If it fails, retry with appropriate fallback settings\n"
        "- Report files changed and test results\n"
        "\n"
        "TASK:\n"
        "Implement OAuth refresh flow..."
    )
)
```

This pattern:

- Keeps the PM's context clean
- Isolates the coding agent session
- Lets the PM monitor or abort without blocking
- Enables parallel work (other subagents can run concurrently)

Direct invocation (without subagent wrapper) is acceptable only for: smoke tests, one-liner verifications, or when `delegate_task` is genuinely unavailable (e.g., toolset disabled, depth limit hit).

---

## 6. Related Skills

| Skill | Role |
| ----- | ---- |
| `hermes-agent` | Hermes Agent configuration, extension, and usage |
| `git-workflow` | ghq + worktree mode, branch management, PR conventions |
| `specification-authoring` | Spec authoring, auditing, and review |
| `opencode` | Code review and implementation via the OpenCode CLI |
