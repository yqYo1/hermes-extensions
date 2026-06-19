---
name: system-design
description: "System design: configuration systems, documentation maintenance, and agent behavior design."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [system-design, configuration, documentation, soulmd, design-patterns]
    related_skills: [software-development-workflow, specification-authoring, hermes-agent]
---

# System Design

System design workflows: configuration file systems, documentation maintenance, and agent behavior specification via SOUL.md.

## When to Use

Load this skill when the user wants to:
- Design a configuration system for an application
- Set up documentation maintenance workflows
- Create or refine a SOUL.md for agent behavior
- Design extensible event systems
- Plan configuration migration strategies

## 1. Configuration System Design

### Design Principles

- **Static vs Dynamic**: Separate static config (files) from dynamic config (runtime)
- **Priority Chain**: Define clear precedence (defaults < file < env < CLI args)
- **Validation**: Validate config at load time, not at use time
- **Documentation**: Every config option must be documented

### Configuration Patterns

**Layered Configuration:**
```
Default Config  →  File Config  →  Environment  →  CLI Args
     │                │               │              │
     ▼                ▼               ▼              ▼
   Base values    User prefs     Secrets      Overrides
```

**Dynamic Configuration:**
- Hot-reload without restart
- Change notifications
- Rollback capability
- Audit logging

### Key Design Decisions

See `references/config-priority-merging.md` for priority merging patterns.
See `references/dynamic-config-examples.md` for dynamic configuration examples.
See `references/event-system-design-decisions.md` for event system design.
See `references/keymap-api-design.md` for keymap API design patterns.
See `references/lsp-configuration-for-dynamic-configs.md` for LSP integration.

## 2. Documentation Maintenance

### Keeping Docs in Sync

Documentation drifts from code over time. Use these practices:

1. **Doc-driven development** — Write docs before code
2. **Auto-generation** — Generate API docs from code
3. **CI checks** — Fail builds when docs are stale
4. **Regular audits** — Schedule doc review sessions

### Documentation Types

| Type | Audience | Update Frequency |
|------|----------|-----------------|
| README | New users | Every major feature |
| API docs | Developers | Every API change |
| Architecture | Contributors | Every structural change |
| Runbooks | Operators | Every operational change |
| Changelog | Users | Every release |

### Verification

See `references/github-verification.md` for GitHub-based doc verification workflows.

## 3. SOUL.md Design

SOUL.md defines agent behavior, constraints, and personality. It's the "constitution" for an AI agent.

### Structure

```markdown
# SOUL.md

## Identity
Who the agent is, its role, and purpose.

## Constraints
Hard rules that must never be violated.

## Behavioral Rules
How the agent should behave in specific situations.

## Tool Usage
When and how to use specific tools.

## Communication Style
How the agent should communicate with users.

## Error Handling
How to handle failures and edge cases.
```

### Design Principles

- **Specific over general** — "Always use X" beats "Consider using X"
- **Actionable** — Rules should be checkable
- **Prioritized** — Order rules by importance
- **Minimal** — Fewer rules are easier to follow

### Common Patterns

See `references/soulmd-conflict-analysis.md` for resolving conflicts in SOUL.md rules.
See `references/u-curve-optimization.md` for optimizing rule specificity.

## Pitfalls

1. **Over-engineering config** — Start simple, add complexity only when needed
2. **Docs as afterthought** — Write docs while coding, not after
3. **Vague SOUL.md rules** — "Be helpful" is not a useful constraint
4. **Config without validation** — Invalid config should fail fast
5. **Documentation silos** — Keep related docs together

## Related Skills

- **software-development-workflow**: Planning and implementation
- **specification-authoring**: Writing formal specifications
- **hermes-agent**: Hermes-specific configuration and behavior
