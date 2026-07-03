# subagent-policy skill — supplementary reference

This README contains configuration reference, diagnostics guidance, and
operational troubleshooting for the subagent-policy skill. It is not loaded
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
