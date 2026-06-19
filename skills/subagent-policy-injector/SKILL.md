---
name: subagent-policy-injector
description: "Uses the subagent-policy-injector Hermes plugin to inject sub-agent operation policy skills into every LLM call via the pre_llm_call hook."
version: 1.0.0
author: yqYo1
license: MIT
metadata:
  hermes:
    tags: [subagent, policy, inject, context, pre-llm-call, plugin]
    related_skills: [hermes-plugin-development, subagent-operation-policy, subagent-driven-development]
---

# Subagent Policy Injector Plugin

Injects configured sub-agent operation policy skills into every LLM call via the
`pre_llm_call` hook. Looks up skills in `~/.hermes/skills/` and injects their content
so sub-agents always have the correct operation policy instructions.

## Plugin Location

- Repo: `~/ghq/github.com/yqYo1/hermes-extensions/plugins/subagent-policy-injector/`
- Symlink: `~/.hermes/plugins/subagent-policy-injector/` → repo path

## Installation

```bash
# 1. Create activation symlink
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/subagent-policy-injector \
      ~/.hermes/plugins/subagent-policy-injector

# 2. Enable the plugin
hermes plugins enable subagent-policy-injector

# 3. Add config to ~/.hermes/config.yaml
```

## Configuration

Add to `~/.hermes/config.yaml`:

```yaml
plugins:
  subagent_policy_injector:
    enabled: true

    # Skill names to inject as operation policy.
    # Looked up in ~/.hermes/skills/<category>/<name>/SKILL.md
    # or ~/.hermes/skills/<name>/SKILL.md.
    policy_skills:
      - subagent-operation-policy

    # Template for the injection suffix.
    # {content} is replaced with the resolved skill content.
    suffix_template: |
      [sub-agent operation policy]
      Follow the operation policy described below:

      {content}

    # Only inject on the first turn of each session (default: true).
    inject_once: true
```

## Behavior

- On `pre_llm_call`, loads each configured policy skill from `~/.hermes/skills/`
- Injects the skill content as a suffix with an instruction to follow the policy
- If `inject_once` is true (default), only injects on the first turn of each session
- On session end/reset, clears the priming flag

## Use Case

When the main agent delegates tasks to sub-agents, this plugin ensures every
sub-agent LLM call includes the correct operation policy instructions, preventing
sub-agents from fabricating results, going off-scope, or violating branch discipline.

## Lifecycle

- `pre_llm_call` — fires once per user turn. Loads and injects policy skills.
- `on_session_end` / `on_session_reset` — clears the priming flag for the session.

## Dependencies

- Hermes Agent (plugin system)
- `hermes_cli.config.load_config` (Hermes built-in)
- Access to `~/.hermes/skills/` for skill resolution

## References

- `references/pre-llm-call-context-injection.md` — Source-level mechanics of pre_llm_call
