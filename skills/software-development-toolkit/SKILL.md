---
name: software-development-toolkit
description: "Software development toolkit: workflows, testing, Rust development, event systems, memory management, and system design."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [software-development, testing, rust, events, memory, system-design, workflows]
---

# Software Development Toolkit

Umbrella skill for software development: workflows, testing, Rust development, event systems, memory management, and system design.

## Sub-Domains

### Development Workflows

- **Software Development Workflow** — Planning, TDD, debugging, git workflows. See `references/software-development-workflow.md`.
- **Subagent-Driven Development** — Execute plans via delegate_task subagents. See `references/subagent-driven-development.md`.

### Testing

- **Embedded Firmware Testing** — Test embedded firmware and host-side sender code. See `references/embedded-firmware-testing.md`.
- **Python Headless GUI Testing** — Test Python GUI code in headless environments. See `references/python-headless-gui-testing.md`.

### Rust Development

- **Rust Development** — Rust application development with build-time code generation. See `references/rust-development.md`.
- **Rust Embedded Scripting** — Embed scripting runtimes (Lua, Python) in Rust. See `references/rust-embedded-scripting.md`.

### System Design

- **Extensible Event Systems** — Design event-driven hook systems with Pre/Post phases. See `references/extensible-event-systems.md`.
- **Memory Management** — Rules for saving and managing persistent memory. See `references/memory-management.md`.
- **System Design** — Configuration systems and documentation maintenance. See `references/system-design.md`.

## Choosing the Right Tool

| Goal | Tool | Use Case |
|------|------|----------|
| Development workflow | Software Development Workflow | TDD, debugging, git |
| Parallel development | Subagent-Driven Development | delegate_task patterns |
| Firmware testing | Embedded Firmware Testing | Embedded code testing |
| GUI testing | Python Headless GUI Testing | tkinter/etc in headless |
| Rust projects | Rust Development | Rust app development |
| Script embedding | Rust Embedded Scripting | Lua/Python in Rust |
| Event systems | Extensible Event Systems | Hook-based architecture |
| Memory management | Memory Management | Persistent memory rules |
| System design | System Design | Config systems, docs |

## References

- `references/software-development-workflow.md` — Development workflows
- `references/subagent-driven-development.md` — Subagent patterns
- `references/embedded-firmware-testing.md` — Firmware testing
- `references/python-headless-gui-testing.md` — GUI testing
- `references/rust-development.md` — Rust development
- `references/rust-embedded-scripting.md` — Script embedding
- `references/extensible-event-systems.md` — Event systems
- `references/memory-management.md` — Memory management
- `references/system-design.md` — System design
