---
name: python-headless-gui-testing
description: "Test Python GUI code (tkinter, etc.) in headless environments without the GUI framework installed."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Python, Testing, tkinter, GUI, Headless, Mock]
    related_skills: [test-driven-development, opencode]
---

# Headless Python GUI Testing

Run tests for Python code that imports `tkinter`, `PyQt`, or other GUI frameworks on CI servers or containers that lack X11/windowing systems.

## Core Technique: `sys.modules` Pre-Seeding

Before the code-under-test imports `tkinter`, inject a fully-mocked module into `sys.modules`. This prevents `ModuleNotFoundError` and satisfies attribute lookups.

### Minimal tkinter Mock

```python
import sys
import types
from unittest.mock import MagicMock

# Build a mock tkinter module
_mock_tk = types.ModuleType("tkinter")
for name in [
    "Label", "Button", "Entry", "Frame", "StringVar", "IntVar",
    "Checkbutton", "OptionMenu", "Radiobutton", "Spinbox", "Scale",
    "Combobox", "Scrollbar", "Canvas", "PhotoImage", "Tk", "Menu",
    "Menubutton", "Message", "PanedWindow", "Toplevel",
    "simpledialog", "colorchooser", "filedialog", "font",
    "N", "S", "E", "W", "NW", "NE", "SW", "SE",
]:
    setattr(_mock_tk, name, MagicMock)

# Sub-modules
_mock_tkf = types.ModuleType("tkinter.filedialog")
_mock_tkf.askopenfilename = MagicMock(return_value="")
sys.modules["tkinter.filedialog"] = _mock_tkf
sys.modules["tkinter.ttk"] = _mock_tk

# Must be last — after sub-modules are ready
sys.modules["tkinter"] = _mock_tk
```

**Place this in `conftest.py` (pytest) or at the very top of the test file**, before any import that transitively pulls in `tkinter`.

## Full Production Example

See `references/conftest-tkinter-mock.py` for a battle-tested `conftest.py` used in a real project (Poke-Controller Extension). It mocks:

- `tkinter` and all standard widgets
- `tkinter.filedialog`, `tkinter.messagebox`, `tkinter.simpledialog`
- `plyer` (desktop notifications)
- Project-specific modules (`DiscordNotify`, `LineNotify`, `PokeConDialogue`, `Settings`, `ExternalTools`, `gui.assets`)

## Common Mock Patterns

| What to Mock | How |
|---|---|
| Widget classes | `MagicMock` class (instantiable, callable) |
| Dialog functions | `MagicMock(return_value=...)` |
| Module-level constants | `setattr(_mock, "CONST", value)` |
| Sub-packages | Create `types.ModuleType(name)`, populate, then `sys.modules[name] = mod` |

## Verification

Run the test suite in a container without `python3-tk`:

```bash
# Debian/Ubuntu — do NOT install python3-tk
apt-get install python3-pytest python3-numpy  # tkinter intentionally omitted
pytest tests/ -v
```

If `ModuleNotFoundError: No module named 'tkinter'` still occurs, the mock was not injected **before** the first `import tkinter` (or transitive import). Check import order with `python -X importtime -c "import my_module"`.

## Pitfalls

- **Import order matters**: `sys.modules["tkinter"] = mock` must happen before any code imports it. In pytest, put it at the top of `conftest.py` (no imports of the app above it).
- **MagicMock vs MagicMock()**: Use `MagicMock` (the class, not an instance) for widget classes so that `tk.Label(...)` creates a new mock instance automatically.
- **Nested sub-modules**: Mock leaf modules before parent modules if the parent references them during its own initialization.
