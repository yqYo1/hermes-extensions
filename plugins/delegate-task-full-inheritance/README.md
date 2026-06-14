# delegate-task-full-inheritance

Hermes Agent plugin that prevents limiting toolsets in `delegate_task` calls.

## Purpose

Forces subagents to inherit the parent's full toolset. This prevents unintended capability restrictions caused by toolset limitation.

## Behavior

- Blocks when `toolsets` parameter is present in `delegate_task`
- Supports both single-task mode and batch mode detection
- Block reason is returned as a tool error and **notified to the LLM as well**
- The LLM can retry without the `toolsets` restriction

## Block Message Examples

### Single-task mode

```
delegate_task with explicit 'toolsets' parameter is blocked. Subagents must inherit the parent's full toolset. Remove the 'toolsets' parameter to allow full inheritance.
```

### Batch mode

```
delegate_task batch mode: task 0 has explicit 'toolsets' parameter. Subagents must inherit the parent's full toolset. Remove 'toolsets' from task 0 to allow full inheritance.
```

## Installation

```bash
# Symlink installation (recommended)
ln -s ~/ghq/github.com/yqYo1/hermes-extensions/plugins/delegate-task-full-inheritance ~/.hermes/plugins/

# Enable
hermes plugins enable delegate-task-full-inheritance
```

## Configuration

Check enabled status in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - delegate-task-full-inheritance
```

New sessions (`/reset`) will load the plugin.

## License

MIT License
