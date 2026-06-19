---
name: rust-embedded-scripting
description: "Embed scripting runtimes (Lua, Python) in Rust applications: mlua API registration, PyO3 bindings, async callback bridging, and JSON value conversion."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [rust, lua, python, pyo3, mlua, scripting, embedding, ffi, bindings]
    related_skills: [nix-flake-devops]
---

# Rust Embedded Scripting

Embed Lua and Python scripting runtimes in Rust applications. Covers mlua (Lua-in-Rust), PyO3 (Python-in-Rust), callback bridging across thread boundaries, async runtime integration, and JSON value conversion.

## When to Use

- Your Rust application needs a user-extensible scripting layer
- You want users to write configuration or event handlers in Lua or Python
- You need to maintain Python API compatibility while migrating to Rust core
- You have a Rust event system and want scripts to participate in it
- You need async-safe access to a scripting runtime from a tokio runtime

---

## 1. Lua-in-Rust (mlua)

### Workspace Setup

```toml
[workspace.dependencies]
mlua = { version = "0.10", features = ["lua54", "vendored", "async"] }
parking_lot = { workspace = true }
```

**Feature notes:**
- `lua54` — Lua 5.4 interpreter. Use `luajit` for LuaJIT.
- `vendored` — Bundles Lua source for portability.
- `async` — Enables `call_async()`. Required if wrapping `Lua` behind `tokio::sync::Mutex`.

### API Table Registration

```rust
use mlua::{Lua, Result as LuaResult, Table, Value};

pub fn register_api(lua: &Lua) -> LuaResult<()> {
    let api = lua.create_table()?;
    api.set("hello", lua.create_function(|_, name: String| {
        println!("Hello, {}!", name);
        Ok(())
    })?)?;
    api.set("add", lua.create_function(|_, (a, b): (i64, i64)| Ok(a + b))?)?;
    lua.globals().set("myapp", api)?;
    Ok(())
}
```

### Async LuaRuntime (Arc<Mutex<Lua>>)

```rust
use std::sync::Arc;
use tokio::sync::Mutex;

pub struct LuaRuntime {
    lua: Arc<Mutex<Lua>>,
}

impl LuaRuntime {
    pub fn new() -> Result<Self, LuaRuntimeError> {
        Ok(Self { lua: Arc::new(Mutex::new(Lua::new())) })
    }

    pub async fn call_function<A: mlua::IntoLuaMulti>(
        &self, name: &str, args: A,
    ) -> Result<mlua::Value, LuaRuntimeError> {
        let lua = self.lua.lock().await;
        let func: mlua::Function = lua.globals().get(name)?;
        let result = func.call_async(args).await?;
        Ok(result)
    }
}
```

### Lua↔JSON Value Conversion

```rust
fn json_value_to_lua(lua: &Lua, val: &serde_json::Value) -> mlua::Result<mlua::Value> {
    match val {
        serde_json::Value::Null => Ok(mlua::Value::Nil),
        serde_json::Value::Bool(b) => Ok(mlua::Value::Boolean(*b)),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() { Ok(mlua::Value::Integer(i)) }
            else if let Some(f) = n.as_f64() { Ok(mlua::Value::Number(f)) }
            else { Ok(mlua::Value::Nil) }
        }
        serde_json::Value::String(s) => Ok(mlua::Value::String(lua.create_string(s)?)),
        serde_json::Value::Array(arr) => {
            let tbl = lua.create_table()?;
            for (i, v) in arr.iter().enumerate() {
                tbl.set(i + 1, json_value_to_lua(lua, v)?)?;
            }
            Ok(mlua::Value::Table(tbl))
        }
        serde_json::Value::Object(map) => {
            let tbl = lua.create_table()?;
            for (k, v) in map { tbl.set(k.as_str(), json_value_to_lua(lua, v)?)?; }
            Ok(mlua::Value::Table(tbl))
        }
    }
}
```

### Callback Bridging: The Critical Pattern

**The problem:** `mlua::Function` is `!Send + !Sync`. Cannot pass directly to APIs requiring `Send + Sync + 'static` handlers.

**The solution:** Two-level callback registry:

1. Store actual `mlua::Function` objects in the **Lua named registry**, identified by integer keys.
2. Maintain a **Rust-side `Arc<Mutex<HashMap<String, Vec<usize>>>>`** mapping event names to integer keys.
3. When dispatching, lock Lua, look up keys, retrieve functions from registry, and call them.

```rust
use std::sync::Arc;
use parking_lot::Mutex;
use std::collections::HashMap;

pub struct ApiHandle {
    pub event_bus: Option<EventBus>,
    pub lua_callbacks: Arc<Mutex<HashMap<String, Vec<usize>>>>,
}

impl ApiHandle {
    pub fn store_callback(lua: &Lua, func: &LuaFunction) -> usize {
        let registry = lua.named_registry_value::<Table>("callbacks").ok();
        if let Some(reg) = registry {
            let next_key: usize = reg.get("__next_key").unwrap_or(1);
            reg.set("__next_key", next_key + 1).ok();
            reg.set(next_key, func.clone()).ok();
            next_key
        } else { 0 }
    }
}
```

**Key constraint:** Both storage and dispatch MUST happen while holding the Lua mutex lock.

### Common Pitfalls

- `!Send + !Sync` on LuaFunction — use the callback registry workaround
- Lua infinite loops cannot be tokio-preempted — design scripts to be cooperative
- Callback registry must be initialised before first use
- Clone-under-lock pattern for callback lists to prevent deadlocks

---

## 2. Python-in-Rust (PyO3)

### Workspace Setup

```toml
[workspace.dependencies]
pyo3 = { version = "0.25", features = ["extension-module", "py-clone"] }
```

**`py-clone`** is needed whenever you clone `PyObject` (e.g., storing callbacks in a `Vec<PyObject>` inside `Mutex`).

### Basic PyO3 Module

```rust
use pyo3::prelude::*;

#[pyfunction]
fn hello(name: &str) -> PyResult<String> {
    Ok(format!("Hello, {}!", name))
}

#[pymodule]
fn my_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello, m)?)?;
    Ok(())
}
```

### NumPy Array Interop

```rust
use numpy::{PyArray3, PyArrayMethods, PyUntypedArrayMethods};
use pyo3::prelude::*;

#[pyfunction]
fn process<'py>(py: Python<'py>, img: &Bound<'py, PyArray3<u8>>) -> PyResult<Bound<'py, PyArray3<u8>>> {
    let arr = img.readonly();
    let shape = arr.shape();
    let out = ndarray::Array3::zeros((shape[0], shape[1], shape[2]));
    Ok(PyArray3::from_owned_array(py, out))
}
```

**Trait imports needed:** `PyArrayMethods` for `.readonly()`, `PyUntypedArrayMethods` for `.shape()`.

### Named Constants via #[classattr]

```rust
#[pyclass(eq)]
#[derive(Clone, PartialEq)]
struct Button {
    inner: RustButton,
}

#[pymethods]
#[allow(non_snake_case)]
impl Button {
    #[new]
    fn new(value: u16) -> Self { ... }

    #[classattr]
    fn A() -> Self { Self { inner: RustButton::A } }
}
```

### Callback Storage (Python → Rust)

```rust
#[pyclass]
struct EventBus {
    callbacks: Mutex<HashMap<String, Vec<PyObject>>>,
}

#[pymethods]
impl EventBus {
    fn on(&self, event_type: String, callback: PyObject) -> PyResult<()> {
        let mut inner = self.callbacks.lock().unwrap();
        inner.entry(event_type).or_default().push(callback);
        Ok(())
    }

    fn emit(&self, py: Python<'_>, event_type: String, data: String) -> PyResult<()> {
        let callbacks: Vec<PyObject> = {
            let inner = self.callbacks.lock().unwrap();
            inner.get(&event_type).cloned().unwrap_or_default()
        };
        for cb in &callbacks {
            cb.bind(py).call((event_type.clone(), data.clone()), None)?;
        }
        Ok(())
    }
}
```

**Key pattern:** Clone the callback list under the lock, then release before calling into Python.

### Build & Install

```bash
# Editable install (development)
uv run maturin develop

# Production wheel
uv run maturin build --release
```

### Common PyO3 Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `no method named readonly found` | Missing trait import | `use numpy::PyArrayMethods;` |
| `from_owned_array_bound` not found | API changed in numpy 0.25 | Use `from_owned_array` |
| `new_bound` not found for PyModule | API changed in pyo3 0.25 | Use `PyModule::new` |
| `eq_int` can only be used on simple enums | Applied to struct | Use `#[pyclass(eq)]` without `eq_int` |
| `no method named clone found for Py<T>` | Missing `py-clone` feature | Enable `py-clone` or use `cb.clone_ref(py)` |
| module name must not contain minus | `module-name` missing in pyproject.toml | Add `module-name = "snake_case_name"` |

---

## 3. Python Compatibility Layer (Migration Scenario)

When migrating Python projects to Rust core with PyO3 bindings while maintaining Python API compatibility:

### Metaclass for MRO Injection

```python
class CommandMeta(ABCMeta):
    _registry: dict[str, type] = {}
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Inject Rust adapter into MRO for user subclasses
        ...
```

### Import Hacks for Old Paths

```python
import sys, types
_mod = types.ModuleType("OldPackage.OldModule")
_mod.OldClass = NewClass
sys.modules["OldPackage.OldModule"] = _mod
```

### XDG-Compliant Directory Design

```python
import os
from pathlib import Path

def get_scripts_dir() -> Path:
    if env_path := os.environ.get("APP_SCRIPTS_DIR"):
        return Path(env_path).expanduser().resolve()
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "app" / "scripts"
    return Path.home() / ".config" / "app" / "scripts"
```

**Priority:** CLI arg > env var > XDG config > default > legacy fallback.

---

## 4. Gradual PyO3 Expansion Pattern

When extending PyO3 bindings from skeleton to full API:

### Stage 0: Skeleton (Module Registration)
```rust
#[pymodule]
fn my_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let sub = PyModule::new(m.py(), "submodule")?;
    m.add_submodule(&sub)?;
    Ok(())
}
```

### Stage 1: Core Types (Enums, Simple Structs)
Export Rust enums/structs with basic methods first.

### Stage 2: Callback-Based Classes
Add Python-side callback registration and triggering.

### Stage 3: Delegation to Rust Core
Add methods that delegate to Rust core crates. Use a lazy-initialized tokio runtime for async bridging:

```rust
fn get_runtime(&self) -> PyResult<Runtime> {
    let mut rt_guard = self.runtime.lock().map_err(|e| {
        PyRuntimeError::new_err(format!("Mutex poisoned: {}", e))
    })?;
    if rt_guard.is_none() {
        *rt_guard = Some(Runtime::new().map_err(|e| {
            PyRuntimeError::new_err(format!("Failed to create tokio runtime: {}", e))
        })?);
    }
    Ok(rt_guard.as_ref().unwrap().clone())
}
```

### Stage 4: Notification/Network Integration
Add Discord, Line, or other external service integrations.

---

## 5. Rust/Python Boundary Decision Framework

When migrating a Python project to Rust core with PyO3 bindings, use this framework to decide what goes where:

### Core Principle

> **"If it doesn't need to be Python, it should be Rust."**

The Python compatibility layer should be as thin as possible — only user-facing APIs and import-path compatibility.

### Decision Matrix

| Factor | Rust (PyO3) | Python (Compatibility Layer) |
|--------|-------------|------------------------------|
| Performance-critical code | ✅ Yes | ❌ No |
| Hardware I/O (serial, camera) | ✅ Yes | ❌ No |
| Image processing | ✅ Yes | ❌ No |
| User script base classes | ⚠️ PyO3 + metaclass | ✅ Import hacks |
| User script imports (`Button`, `Hat`) | ✅ PyO3 enums | ❌ No pure-Python fallback needed |
| Internal-only classes (`KeyPress`) | ✅ Yes, rename freely | ❌ No need to preserve name |
| `self.keys.neutral()` — user-facing | ✅ PyO3 method | ❌ Not needed |
| `self.keys.ser.writeRow()` — user-facing | ✅ PyO3 method | ❌ Not needed |
| `self.keys.ser.ser.write()` — pySerial compat | ✅ PyO3 wrapper | ❌ Not needed |
| Type conversion (Python → Rust) | ✅ PyO3 `FromPyObject` | ❌ Not needed |
| Dialog wrappers (`dialogue()`, etc.) | ⚠️ Delegate to tkinter | ✅ Python wrapper |
| Print/log methods | ⚠️ Rust core + Python shim | ✅ Thin wrapper |

### Key Rules

1. **User script API surface**: Expose via PyO3 with exact same names/signatures
2. **Internal-only classes**: Move to Rust, rename freely, expose only what's needed
3. **pySerial compatibility**: Create PyO3 wrapper that mimics pySerial API (`ser.write()`, `ser.writeRow()`)
4. **Type conversion**: Handle in PyO3 (`FromPyObject`/`ToPyObject`), not in Rust core
5. **Metaclass for dynamic dispatch**: Keep in Python for flexibility, delegate to Rust implementations

### Example: Sender Class Migration

```rust
#[pyclass]
struct PySender {
    inner: RustSender,  // Rust core serial manager
}

#[pymethods]
impl PySender {
    fn writeRow(&self, row: &str) -> PyResult<()> {
        self.inner.write_row(row)
            .map_err(|e| PyOSError::new_err(e.to_string()))
    }
    
    #[getter]
    fn ser(&self) -> PySerialWrapper {
        PySerialWrapper { inner: self.inner.raw_serial() }
    }
}

#[pyclass]
struct PySerialWrapper {
    inner: RawSerial,
}

#[pymethods]
impl PySerialWrapper {
    fn write(&self, data: &Bound<'_, PyAny>) -> PyResult<()> {
        // PyO3 handles type conversion from str/bytes/list to bytes
        let bytes = python_data_to_bytes(data)?;
        self.inner.write(&bytes)
            .map_err(|e| PyOSError::new_err(e.to_string()))
    }
}
```

## 6. Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|--------------|------------------|
| Passing `mlua::Function` across threads | `!Send + !Sync` | Use named registry + integer keys |
| Using `std::sync::Mutex` across await points | Compilation error | Use `tokio::sync::Mutex` |
| Mocking `MagicMock` for `isinstance()` | `MagicMock` is not a type | Use metaclass-based mock with real types |
| `rng.gen()` in Rust 2024 edition | `gen` is reserved keyword | Use `rng.r#gen()` or `rng.random()` |
| Missing `[[bench]] harness = false` | Conflicts with criterion's `main()` | Explicit bench declarations |
| Module name mismatch between Rust and Python | Import failures | Ensure `pyproject.toml` `module-name` matches `#[pymodule]` fn name |
| Keeping internal classes in Python "for compatibility" | Defeats Rust migration purpose | Move to Rust, expose via PyO3 only what's needed |
| Preserving bad architecture during migration | Perpetuates design debt | Re-design in Rust, provide thin compat layer |

---

## References

- `references/mlua-callback-bridging.md` — Full worked example of callback bridging with EventBus integration
- `references/pyo3-gradual-expansion.md` — Staged approach to expanding PyO3 bindings
- `references/mock-isinstance-pattern.md` — MagicMock isinstance() pattern for Python 3.14+
- `references/xdg-directory-design.md` — XDG Base Directory script directory pattern
- `references/rust-2024-reserved-keywords.md` — Rust 2024 edition reserved keywords
- [mlua crate docs](https://docs.rs/mlua/)
- [PyO3 User Guide](https://pyo3.rs/)
- [Maturin Documentation](https://www.maturin.rs/)
