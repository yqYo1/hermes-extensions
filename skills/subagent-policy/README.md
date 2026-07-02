# subagent-policy skill — design notes

This README documents the *why* behind decisions in `SKILL.md`. It is not loaded
at runtime and does not consume skill context; it exists for maintainers.

## Configuration

The following `delegation.*` settings in `~/.hermes/config.yaml` control subagent
behaviour.

| Key | Default | Description |
| --- | ------- | ----------- |
| `child_timeout_seconds` | `0` (unlimited) | Max seconds a subagent may run before timing out |
| `subagent_auto_approve` | `false` | Auto-approve tool calls (bypass confirmation prompts) |
| `max_iterations` | `50` | Max tool-call iterations per subagent before forced return |
| `max_concurrent_children` | `12` | Max children spawned in a single synchronous batch |

Values are set via:

```bash
hermes config set delegation.child_timeout_seconds 300
hermes config set delegation.subagent_auto_approve true
```

Changes to `delegation.*` take effect immediately on the next `delegate_task`
call; no session restart is required.

## Diagnostics

When timeout diagnostics are opted in, timeout events are logged to:

```
~/.hermes/logs/subagent-timeout-*.log
```

## Troubleshooting

### Copilot ACP: "Could not start Copilot ACP command"

**Symptom:** `delegate_task` fails immediately with
`Could not start Copilot ACP command`.

**Resolution:** Ensure the Copilot ACP process is running and accessible from
the same environment where Hermes is executing.

---

## Why `toolsets` cannot be specified (§3.2)

`SKILL.md` states only the fact: the `toolsets` parameter is rejected at
runtime and must be omitted. The reason is intentionally not in the skill:

- The enforcement is implemented by the `delegate-task-full-inheritance` plugin
  (in `plugins/delegate-task-full-inheritance/` of this repository).
- The plugin's `pre_tool_call` hook blocks any `delegate_task` call that passes
  an explicit `toolsets` parameter, in both single-task and batch (`tasks[]`)
  modes, and returns the block as a tool error so the LLM retries without it.
- The policy ensures subagents always inherit the parent's full toolset,
  preventing unintended capability restrictions.

The skill omits the plugin name because the LLM only needs to know the
constraint (do not pass `toolsets`), not the implementation that enforces it.

## Why no concurrency calculation example (former §2.2)

Earlier versions included a Depth 0/1/2 computation (up to 157 subagents). It
was removed because the PM only decides how many *direct* children (Depth 1) to
spawn; grandchildren (Depth 2) are the responsibility of orchestrator children.
The `max_concurrent_children` row in §2.1 is the only number the PM needs.

## Why the skill is minimal

Per `AGENTS.md`, skills consume context at runtime, so `SKILL.md` contains
only what the LLM needs to act. Everything below was intentionally moved here:

- **Plugin name / enforcement rationale (§3.2)** — the LLM only needs the fact
  that `toolsets` is rejected; the enforcing plugin name is implementation
  detail.
- **Source-of-values note (former §2.1 footnote)** — "current values come from
  `~/.hermes/config.yaml`" is maintainer context.
- **Per-tool block reasons (former §3.3 "Reason" column)** — design rationale;
  the LLM only needs to know *which* tools are blocked, not *why*.
- **Mitigation column and internal flags (former §4.1)** — `skip_memory=True`,
  `skip_context_files=True`, etc. are implementation flags. The skill states
  only what is not inherited and that `context` is the channel for passing
  missing info.
- **"Lost in the middle" note (former §5.1)** — LLM behavior the model already
  knows; not actionable skill content.

## Skill content policy

Per `AGENTS.md`, skills in this repository are written in English by default
and contain only what the LLM needs at runtime. Background, rationale, and
implementation references live here in the README.
