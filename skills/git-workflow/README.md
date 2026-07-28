# Git Workflow Skill

## Maintainer Notes

`SKILL.md` contains only the rules and decision boundaries needed while executing
the workflow. This file records design rationale that should be preserved for
future maintainers but does not need to be loaded at runtime.

### Dedicated Worktrees for Delegated Repository Writes

Delegated tasks that may write inside a Git working tree or mutate local branch,
index, or commit history are always isolated in a dedicated subagent worktree.
Subagents may be assigned lower-cost models than the main agent, so the skill
uses one uniform safety boundary instead of making isolation depend on the
worker's actual model or an execution-time capability judgment.

This rationale is intentionally omitted from `SKILL.md`. An agent executing the
skill only needs the mandatory isolation rule, its narrow read-only exception,
and the worktree naming and cleanup procedure.
