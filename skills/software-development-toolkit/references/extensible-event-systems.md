---
title: Extensible Event/Hook System Design
name: extensible-event-systems
description: Design event-driven hook systems with Pre/Post phases, autocmd-style groups, and non-invasive extensibility for applications with scripting layers.
trigger: |
  When designing an event-driven extension mechanism, plugin hook system, or autocmd-style
  lifecycle hooks for an application. Especially relevant when the application has a scripting
  layer (Python, Lua, etc.) and the user wants non-invasive extensibility without monkey-patching.
  Also applies when adding observability, pre/post hooks, or plugin interception points to an
  existing codebase.
---

# Extensible Event/Hook System Design

Design event-driven hook systems that allow users/plugins to intercept and extend application behavior without modifying core code or monkey-patching.

## Core Design Principles

### 1. Pre/Post Phase Hooks

Every hookable operation MUST expose both a **Pre** (before) and **Post** (after) phase:

- **Pre hooks** run after setup/initialization is complete but BEFORE the main operation begins. In Neovim terms: `BufReadPre` fires after the buffer is created but before file content is read.
- **Post hooks** run AFTER the main operation fully completes, including all side effects (tag generation, state updates, etc.).
- Both phases share the same event name prefix (e.g., `CameraConnectPre`, `CameraConnectPost`)
- Handlers subscribe to a specific phase; omitting the phase (or passing `None`) subscribes to both

**Pre/Post boundary definition** (Neovim-inspired):

```
1. Setup phase (path resolution, directory checks)
2. Pre event fires — handlers can mutate candidate lists/state
3. Main operation (file reading, class extraction, tag generation)
4. Post event fires — handlers receive finalized data
```

### 2. Callback Argument Types

All event callbacks receive a unified `dict[str, Any]` (Python) or `table` (Lua) argument:

- Each event defines its own TypedDict/dataclass for the data structure
- LSP-friendly: use `@overload` to map event names to their specific data types
- Example: `ScriptLoadPreData` with `source_dirs` and `candidate_count`; `ScriptLoadPostData` with `commands` list

### 3. State-Based Simplicity

When users need to mutate pre-operation state, prefer simple state properties over elaborate methods:

- **Good**: `pokecon.state.command_candidates = [...]` (user mutates a list directly)
- **Avoid**: `data.exclude(pattern)`, `data.include(path)` (over-engineered API)
- Let users use standard Python/list operations rather than learning custom APIs

### 2. Distinguish System vs. User-Controllable Events

Only event-ify operations that the user/script layer **cannot directly control**:

| Event-ify these | DON'T event-ify these |
|-----------------|----------------------|
| Device connect/disconnect | Button presses initiated by scripts |
| Profile/settings changes | Serial send/receive in script flows |
| Command lifecycle (start/end) | Template matching inside user loops |
| Dialogue open/close | Camera frame processing in script logic |
| External notifications | Any operation the script already sequences |

**Rationale**: If a script can already place code immediately before/after an operation, adding events adds overhead without value. Events are for cross-cutting concerns and system-layer timing.

### 4. Neovim-Inspired API Design (When User Requests)

When the user explicitly requests Neovim-style APIs, model the design after Neovim's actual autocmd system:

**Neovim API Reference**:

- `nvim_create_autocmd(event, opts)` — callback receives `ev` table `{buf, data, event, file, group, id, match}`
- `nvim_del_autocmd(id)` — delete by handler ID
- `nvim_create_augroup(name, {clear=true})` — create group, clear existing if `clear=true`
- `nvim_clear_autocmds(opts)` — clear by group/event/pattern
- `autocmd! [group] [event] [pattern]` — Vimscript clear syntax

**Key Neovim behaviors to replicate**:

- **augroup + autocmd! pattern**: Groups are named containers. `autocmd!` inside a group clears existing commands before adding new ones (prevents duplicate stacking on config reload).
- **Handler ID return**: `on()` returns an opaque handler ID used for `off(id)` deletion.
- **Event-name-based clearing**: `off_all("EventName")` clears all handlers for a specific event (like `autocmd! EventName`).
- **Group-based clearing**: `clear("group_name")` clears all handlers in a group (like `augroup! group_name`).

**Callback signature trade-off**:

- Neovim passes `ev` table to callbacks. User may prefer **argumentless callbacks** to avoid designing argument structure upfront.
- If user chooses argumentless: callbacks access event data via `pokecon.state` or global state. Document this as "default" with "argument-based" as future extension.
- If user chooses argument-based: design `TypedDict` per event type, use `@overload` for LSP-friendly signatures.

**Example (Neovim-inspired, argumentless default)**:

```python
# Register with group
pokecon.autocmd.on("CameraOpenPost", callback=lambda: print("opened"), group="camera")

# Clear all handlers for a specific event (Neovim: autocmd! CameraOpenPost)
pokecon.autocmd.off_all("CameraOpenPost")

# Clear all handlers in a group (Neovim: augroup! camera)
pokecon.autocmd.clear("camera")

# Delete single handler by ID (Neovim: nvim_del_autocmd(id))
pokecon.autocmd.off(handler_id)
```

## Architecture Components

### EventBus

- Thread-safe broadcast channel (e.g., `tokio::sync::broadcast` in Rust, `asyncio.Queue` in Python)
- Decouples event producers from consumers
- Supports fan-out to multiple handlers

### EventRegistry

- Stores handler entries with filters:
  - `event_name`: Exact match or glob/regex pattern
  - `phase`: Pre / Post / Both
  - `pattern`: Optional glob/regex for fine-grained filtering (e.g., device path patterns)
  - `group`: Optional named group for bulk management
  - `once`: Whether to auto-unsubscribe after first fire

### HandlerExecutor

- Dedicated thread pool for handler execution
- **Never block the main thread** (critical for real-time applications)
- Per-handler timeout (default 500ms) to prevent rogue handlers from starving the system
- Exception isolation: one handler's crash must not affect others or the main thread

### NestGuard

- Prevents infinite recursion when a handler emits the same event it just handled
- Track `(event_name, phase, thread_id)` in thread-local/context storage
- Default max nest depth: 1 (drop recursive fires)
- Configurable for advanced use cases

## API Patterns

### Python API (User-Facing)

```python
# Subscribe to a specific phase
self.on("CameraConnect", callback=self._on_cam, phase="Post")

# Subscribe to both phases
self.on("CommandStart", callback=self._on_start)

# One-shot handler
self.once("SerialDisconnect", callback=self._on_disconnect, phase="Post")

# Grouped handlers (batch management)
with self.autocmd_group("debug"):
    self.on("CommandStart", callback=self._log_start, phase="Post")
    self.on("CommandEnd", callback=self._log_end, phase="Post")

# Cleanup
self.autocmd_clear("debug")

# User-originated events
self.emit("MyCustomEvent", data={"foo": "bar"})
```

### Rust Core (Implementation)

```rust
pub struct Event {
    pub name: String,       // e.g., "CameraConnect"
    pub phase: EventPhase,  // Pre / Post
    pub data: serde_json::Value,
    pub timestamp: f64,
    pub source: String,     // crate/module ID
}

pub enum EventPhase { Pre, Post }
```

## Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| Emit overhead | < 1ms main-thread latency | Events must not impact real-time loops (e.g., 60fps camera) |
| Handler timeout | 500ms default | Prevents rogue handlers from blocking the pool |
| Memory growth | Bounded | Use weak refs for handler storage; auto-clear on command end |
| GIL interaction | Release GIL before calling Python callbacks | Essential for Python bindings (PyO3) to avoid blocking Rust threads |

## Implementation Phases

1. **Core crate**: EventBus + Registry + Executor + NestGuard (Rust)
2. **Language bindings**: Expose `on`/`once`/`off`/`emit` via PyO3/ctypes/FFI
3. **Base class integration**: Inject methods into script base classes via metaclass/MRO manipulation
4. **UI integration**: WebSocket push for Web/Tauri debug panels
5. **Testing**: Pre/Post isolation, pattern matching, nest prevention, group cleanup, zero-overhead baseline

## Common Pitfalls

- **High-frequency events**: Camera frame events at 60fps can flood the bus. If frame-level hooks are needed, use a sampling strategy or separate high-frequency channel.
- **GIL deadlock**: Python callbacks that re-enter Rust code can deadlock. Always release GIL before Rust→Python callback transitions.
- **Memory leaks in long-running apps**: Handlers registered in command scope must auto-clear when the command ends. Provide `autocmd_clear` or automatic group teardown on `CommandEndPost`.
- **Over-event-izing**: Resist the urge to add events for every operation. Ask: "Can the script already place code at this exact timing?" If yes, skip the event.

## References

- `references/event-taxonomy-example.md` — Full event taxonomy from a real project (Poke-Controller Extension refactor) showing system-level Pre/Post hooks for device connection, command lifecycle, settings, dialogue, and notifications.
- `references/keymap-system-design.md` — Keymap system design patterns with Neovim-inspired APIs, virtual keys (`<Release-*>`), user-defined keys, and flat API structures for Python/Lua parity.
