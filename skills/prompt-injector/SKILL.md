---
name: prompt-injector
description: "Uses the prompt-injector Hermes plugin to inject custom context (static text, files, skills) into every LLM call via the pre_llm_call hook."
version: 1.0.0
author: yqYo1
license: MIT
metadata:
  hermes:
    tags: [prompt, inject, context, pre-llm-call, plugin]
    related_skills: [hermes-plugin-development]
---

# Prompt Injector Plugin

Injects configured context into every user message via the `pre_llm_call` hook.
Supports three source types: **static text**, **files**, and **skills**.

## Plugin Location

- Repo: `~/ghq/github.com/yqYo1/hermes-extensions/plugins/prompt-injector/`
- Activation symlink: `~/.hermes/plugins/prompt-injector/` → repo path

## Installation

```bash
# 1. Create activation symlink
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/prompt-injector \
      ~/.hermes/plugins/prompt-injector

# 2. Enable the plugin
hermes plugins enable prompt-injector

# 3. Add config to ~/.hermes/config.yaml
```

## Configuration

Add to `~/.hermes/config.yaml`:

```yaml
plugins:
  prompt_injector:
    enabled: true

    # The priming_source is injected only on the first turn of each session.
    # Other sources are injected every turn. Set to null to disable priming.
    priming_source: "always-on-rules"

    sources:
      # === Type 1: Static Text ===
      - type: static
        key: "always-on-rules"
        label: "Always-On Rules"
        text: |
          IMPORTANT: Always verify file paths with git worktree list before editing.
          Always use ghq + worktree workflow.
          Commit and push automatically at work boundaries.
        enabled: true

      # === Type 2: File Content ===
      - type: file
        key: "project-agents"
        label: "Project AGENTS.md"
        path: "/home/yayoi/ghq/github.com/yqYo1/hermes-extensions/AGENTS.md"
        enabled: false

      # === Type 3: Skill Content ===
      - type: skill
        key: "git-workflow-context"
        label: "Git Workflow Context"
        skill_name: "git-workflow"
        enabled: false
```

## Source Types

### Static (`type: static`)

Inline text defined directly in the config. Best for short, always-on behavioral rules.

| Field   | Required | Description        |
|---------|----------|--------------------|
| `text`  | Yes      | The content to inject. Use backtick-pipe-backtick for multi-line YAML strings. |

### File (`type: file`)

Reads content from a file on disk. The file is re-read every turn.

| Field  | Required | Description                              |
|--------|----------|------------------------------------------|
| `path` | Yes      | Absolute path, or relative to HERMES_CWD. Supports `~/` expansion. |

### Skill (`type: skill`)

Loads the SKILL.md content from a skill installed in `~/.hermes/skills/`.

| Field        | Required | Description                                                       |
|--------------|----------|-------------------------------------------------------------------|
| `skill_name` | Yes      | Skill name (matches the skill directory name, not the display name). |

## Priming (First-Turn Only)

The `priming_source` setting designates one source that is injected **only on the first turn** of each session. This is useful for session-start orientation cues that would be redundant on subsequent turns.

Set to `null` or an empty string to disable priming (all sources inject every turn).

## Lifecycle

- `pre_llm_call` — fires once per user turn. All enabled sources are resolved and merged.
- `on_session_end` / `on_session_reset` — clears the priming flag for the session.

## Dependencies

- Hermes Agent (plugin system)
- `hermes_cli.config.load_config` (Hermes built-in)
- Filesystem access for `file` and `skill` source types

## References

- `references/pre-llm-call-context-injection.md` — Source-level mechanics of pre_llm_call
