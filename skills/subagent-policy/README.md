# subagent-policy skill — design notes

This README documents the *why* behind decisions in `SKILL.md`. It is not loaded
at runtime and does not consume skill context; it exists for maintainers.

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

## Skill content policy

Per `AGENTS.md`, skills in this repository are written in English by default
and contain only what the LLM needs at runtime. Background, rationale, and
implementation references live here in the README.
