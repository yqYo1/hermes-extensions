---
name: embedded-firmware-testing
description: "Test embedded firmware (receiver) and host-side sender code by extracting pure logic and exercising state machines without hardware."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [embedded, firmware, testing, pico, sdk, host-tests, extraction, serial, rust, integration-test]
    related_skills: [test-driven-development, systematic-debugging, writing-plans]
---

# Embedded Firmware Testing

## Overview

When testing firmware for microcontrollers (RP2040/RP2350, ESP32, etc.), avoid mocking the entire SDK. Instead, **extract pure logic** into host-testable units.

**Core principle:** If the code doesn't need `pico/stdlib.h`, it doesn't need the Pico SDK to be tested.

## Strategy: Extract Over Mock

### ❌ Don't: Mock the SDK

Creating stubs for `pico/stdlib.h`, `tusb.h`, `hardware/uart.h`, etc.:

- Brittle (stubs drift from real SDK)
- Tedious (hundreds of declarations)
- Tests the wrong thing (stub behavior, not real behavior)

### ✅ Do: Extract Pure Logic

Find the logic that doesn't actually touch hardware:

- Serial protocol parsers
- State machines
- Command dispatchers
- Data transformation pipelines

Move it to standalone C/C++ files with **zero SDK dependencies**.

## Extraction Process

### Step 1: Identify Extractable Logic

Look for functions that:

- Parse buffers/strings into data structures
- Transform data formats
- Make decisions based on parsed values
- Don't call `gpio_put()`, `uart_getc()`, `tud_hid_n_gamepad_report()`, etc.

### Step 2: Create Pure Implementation

```
src/
  serial_parser.h       # No SDK includes
  serial_parser.cpp     # std:: / <cstdint> only
```

Keep the interface minimal:

```cpp
#pragma once
#include <cstdint>

namespace pokecon {

struct GamepadState {
    uint16_t buttons;
    uint8_t  hat;
    uint8_t  lx, ly;
    uint8_t  rx, ry;
};

bool ParseSerialLine(const char* line, GamepadState& state);
void ResetGamepadState(GamepadState& state);

} // namespace pokecon
```

### Step 3: Wire into Firmware

Original file includes and calls the extracted module:

```cpp
#include "serial_parser.h"

static pokecon::GamepadState g_gamepad_state;

void ParseLine(char* line) {
    if (pokecon::ParseSerialLine(line, g_gamepad_state)) {
        pc_report.Hat = g_gamepad_state.hat;
        pc_report.Button = g_gamepad_state.buttons;
        // ... map to HID report
    }
}
```

### Step 4: Preserve Original Behavior

When the original code has quirks that might be intentional:

- Document them in comments
- Reproduce them exactly in the extracted code
- Write tests that verify both the "correct" behavior and the "preserved" behavior

Example: if `use_right & use_left` is bitwise AND in original, reproduce it unless user confirms it's a bug.

## CMake Configuration

Use `BUILD_TESTING` option to conditionally build tests:

```cmake
option(BUILD_TESTING "Build host tests" OFF)

if(NOT BUILD_TESTING)
    # Firmware build (needs Pico SDK)
    include(pico_sdk_import.cmake)
    pico_sdk_init()
    add_executable(PokeControllerForPico ...)
    # ... SDK links
endif()

if(BUILD_TESTING)
    enable_testing()
    set(CMAKE_CXX_STANDARD 17)
    
    include(FetchContent)
    FetchContent_Declare(Catch2 GIT_REPOSITORY https://github.com/catchorg/Catch2.git GIT_TAG v3.8.0)
    FetchContent_Declare(json GIT_REPOSITORY https://github.com/nlohmann/json.git GIT_TAG v3.11.3)
    FetchContent_MakeAvailable(Catch2 json)
    
    add_executable(parser_tests tests/test_parser.cpp src/serial_parser.cpp)
    target_link_libraries(parser_tests PRIVATE Catch2::Catch2WithMain nlohmann_json::nlohmann_json)
    
    include(Catch)
    catch_discover_tests(parser_tests)
endif()
```

## Test Vector Management

### Separate Generation from Execution

Test vectors (serialized inputs + expected outputs) should be:

- **Generated once** using real hardware/tooling
- **Checked into git** as JSON files
- **Loaded by tests** at runtime

```json
{
  "description": "A button only, no stick",
  "input_line": "0x0010 8",
  "expected_buttons": 4,
  "expected_hat": 8,
  "expected_lx": 128,
  "expected_ly": 128,
  "expected_rx": 128,
  "expected_ry": 128
}
```

### Generation Tools

If vectors must be captured from real serial traffic:

- Use `socat` locally to capture raw bytes from the PC-side sender
- Write a one-off Python script to convert raw bytes to JSON
- **Never** run `socat` in CI; it belongs in a local dev script only

## CI Configuration

### Minimal Host-Test Job

```yaml
host-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: sudo apt-get install -y cmake g++
    - run: cmake -B build_test -S . -DBUILD_TESTING=ON
    - run: cmake --build build_test
    - run: ctest --test-dir build_test --output-on-failure
```

**No SDK. No socat. No Python. No Docker.**

### Firmware Build Job

Keep the existing firmware CI unchanged. The extraction should not break it.

## Test Coverage: Go Exhaustive on Extracted Logic

Once the logic is extracted, test every combinatorial surface. Don't settle for "a few happy paths."

### Button Coverage Pattern

For a 14-button mask, test:

- **Each button individually** (14 tests)
- **All buttons together** (1 test: `0xFFFC`)
- **No buttons** (1 test: `0x0000`)
- **Logical groups** (ABXY, LRZLZR, directional cluster, system buttons)
- **Adjacent-bit combinations** (`0x000C`, `0x0030`, `0x00C0`, ...)
- **Alternating-bit patterns** (`0x5554`, `0xAAA8`)
- **With stick flags mixed in** (`0xFFFF`)

### HAT Direction Coverage

Test all 9 directions (0–7 + 8 for center) individually.

### State Transition Tests

For stateful parsers, verify behavior across *sequences* of commands, not just individual parses:

| Pattern | What to verify |
|---------|---------------|
| Set stick → button-only command | Stick value persists unchanged |
| Set stick → overwrite same stick | New value replaces old value |
| Set left → set right | Left persists while right updates, and vice versa |
| Set both → update one only | The other stick persists |
| Rapid button changes with fixed sticks | Stick values remain stable across button-only commands |
| Mixed sequence (stick → button → stick → button) | Each state change is independent |

```cpp
TEST_CASE("Left stick persists through button-only commands") {
    GamepadState state; ResetGamepadState(state);
    ParseSerialLine("0x0002 8 00 00", state);  // set left stick
    REQUIRE(state.lx == 0);
    ParseSerialLine("0x0004 8", state);         // buttons only
    REQUIRE(state.lx == 0);                      // must persist
}
```

### Exhaustive Value Range Tests

For any numeric field with a bounded range (e.g., stick axes 0..255), iterate the *entire* range and verify every value parses correctly:

```cpp
TEST_CASE("Left stick X transitions through all values 0..255") {
    GamepadState state; ResetGamepadState(state);
    for (int x = 0; x <= 255; ++x) {
        char line[32];
        snprintf(line, sizeof(line), "0x0002 8 %02X 80", x);
        REQUIRE(ParseSerialLine(line, state) == true);
        REQUIRE(state.lx == x);
        REQUIRE(state.ly == 128);  // other axis unchanged
    }
}
```

Repeat for:

- Each axis independently (4 loops: LX, LY, RX, RY)
- All axes simultaneously (1 loop where all 4 values are the same)
- Boundary values: 0, 1, 127, 128, 129, 254, 255

This catches off-by-one errors, overflow bugs, and parser digit-handling defects that spot-checking misses.

## Testing the Host-Side Sender (Rust)

The same exhaustive-testing philosophy applies to the **host-side sender crate** that encodes and transmits serial commands. While the firmware parses incoming bytes, the sender must encode them correctly in multiple protocol formats. Both sides need equally thorough coverage.

### The Symmetry

| Concern | Firmware (Receiver) | Host (Sender) |
|---------|-------------------|---------------|
| Serial protocol | Parses incoming lines/bytes | Encodes state into lines/bytes |
| Formats | One target format(s) | May support multiple (Default, Qingpi, 3DS) |
| State machine | Holds button/stick state between commands | Track hold buttons / input state |
| Dependencies | Pico SDK, UART hardware | `tokio-serial`, physical port |
| Testable core | String → struct conversion | Struct → string/bytes conversion |
| Untestable boundary | `uart_getc()` / `tud_hid_n_gamepad_report()` | `SerialStream::write_all()` |

### Strategy: Test State Transitions Through IO Errors

The sender's state machine (`KeyPress` struct) updates internal state **before** the async IO write. This means you can verify state transitions even without a physical serial port — the write will fail with `NotOpen`, but the state has already changed.

```rust
#[tokio::test]
async fn test_hold_adds_button_state() {
    let sender = Sender::new(false);           // no port opened
    let mut kp = KeyPress::new(sender);

    // hold() will update internal state, then fail on write
    let result = kp.hold(&[GamepadInput::SingleButton(Button::A)]).await;
    assert!(matches!(result, Err(SerialError::NotOpen)));

    // State was updated before the IO error
    let held = kp.hold_buttons();
    assert!(held.contains(&GamepadInput::SingleButton(Button::A)));
}
```

**Key insight:** Because state mutations happen *before* the IO call, IO errors don't prevent state verification. This lets you test the full state machine (hold, hold_end, neutral, direction, hat, touchscreen transitions) without mocking or hardware.

### Protocol Encoder Testing

Each serial protocol format is a pure function from `SendFormat` state → output. Test exhaustively:

**Default format (ASCII string):**

```rust
#[test]
fn test_default_empty() {
    let sf = SendFormat::new();
    assert_eq!(sf.convert_to_default(false, false), "0x000000 8");
}

#[test]
fn test_default_with_left_stick_flag() {
    let mut sf = SendFormat::new();
    sf.set_button(&[Button::A]);
    // (btn << 2) | l_stick_flag
    assert_eq!(sf.convert_to_default(true, false), "0x000012 8 80 80");
}
```

**Qingpi format (11-byte binary):**

```rust
#[test]
fn test_qingpi_full_state() {
    let mut sf = SendFormat::new();
    sf.set_button(&[Button::A, Button::B]);       // btn = 0x6
    sf.set_hat(&[Hat::RIGHT]);                    // hat idx 2
    sf.set_any_direction(&[Direction::from_xy(Stick::Left, 200, 50)]);
    sf.set_touchscreen(&[Touchscreen::new(999, 77)]);

    assert_eq!(sf.convert_to_qingpi(), [
        0xAB, 0x06, 0x00, 2, 200, 205, 128, 128, 0xE7, 0x03, 77
    ]);
}
```

**3DS Controller format (6-byte binary with inverted stick encoding):**

```rust
#[test]
fn test_3ds_with_hat_right_and_button() {
    let mut sf = SendFormat::new();
    sf.set_hat(&[Hat::RIGHT]);                    // hat → CONVERT_HAT_3DS[2] = 4
    sf.set_button_3ds_bits(convert_button_3ds(Button::A)); // A → 3DS bit 1

    // byte1 = ((1 & 0xF) << 4) | 4 = 0x14
    assert_eq!(sf.convert_to_3ds(), [0xA1, 0x14, 0, 0xA2, 128, 128]);
}
```

### Rust Integration Test Organization

Structure `tests/integration_test.rs` by concern using inner modules:

```rust
mod button_conversion { /* pure fn tests */ }
mod send_format {
    mod default { /* ASCII string encoding */ }
    mod qingpi { /* binary 11-byte encoding */ }
    mod _3ds { /* binary 6-byte encoding */ }
}
mod keypress_state_machine { /* async state transitions */ }
```

This keeps tests grouped and makes failures easy to locate. Each module reuses imports from the parent scope.

### Error Handling: Differentiating `io::ErrorKind`

When opening a serial port, the underlying `io::Error` carries kind information that should be surfaced as distinct variants:

```rust
#[derive(Error, Debug)]
pub enum SerialError {
    #[error("Serial port not found: {0}")]
    PortNotFound(String),
    #[error("Permission denied opening serial port: {0}")]
    PermissionDenied(String),
    #[error("Failed to open serial port: {0}")]
    OpenError(io::Error),
    #[error("Failed to write to serial port: {0}")]
    WriteError(io::Error),
    #[error("Serial port operation timed out")]
    Timeout,
    #[error("Serial port is not open")]
    NotOpen,
    #[error("Unsupported OS")]
    UnsupportedOS,
}
```

Map errors in the `open()` method:

```rust
let port = match tokio_serial::new(&path, baudrate).open_native_async() {
    Ok(p) => p,
    Err(e) => {
        let io_err: io::Error = e.into();
        return Err(match io_err.kind() {
            io::ErrorKind::NotFound => SerialError::PortNotFound(path),
            io::ErrorKind::PermissionDenied => SerialError::PermissionDenied(path),
            _ => SerialError::OpenError(io_err),
        });
    }
};
```

This gives callers the ability to handle each case differently (e.g., suggest a different port name vs. suggest `chmod`).

### Format String Gotcha: `{:#08x}` in Rust

`format!("{:#08x}", value)` pads to **width 8 including the `0x` prefix**, producing only 6 hex digits:

- `0` → `"0x000000"` (not `"0x00000000"`)
- `0x12` → `"0x000012"` (not `"0x00000012"`)

To get 8 hex digits (32-bit), use `{:#010x}` instead. Account for this in test expectations.

### Reference

- `references/host-side-sender-testing.md` — Full 54-test Rust integration suite for the Poke-Controller serial sender crate.

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Global variable accumulation | Initialize locals every parse call |
| Bitwise vs logical AND | Reproduce original behavior; test both |
| Stick values shifted to wrong field | Match original string position mapping |
| `.gitignore` ignores everything | Add `!/tests/`, `!/tests/**` |
| CMake fetches on every configure | FetchContent caches in `build/_deps` |
| Extracted source missing from firmware target | Add `src/serial_parser.cpp` to BOTH the test `add_executable()` and the firmware `add_executable()` |
| CI job for vector regeneration | **Do not create.** Generate vectors locally, check them into git, and load them in CI. No `socat` in CI ever. |
| Incomplete button coverage | Write individual tests for every bit in the mask, plus all-ON and all-OFF |
| Test vectors drift from protocol | Capture from real Extension sender once, then freeze in JSON |
| Right-stick-only assignment quirk | When `use_right` alone, original code assigns string positions 3/4 to rx/ry. Preserve if user confirms it's intentional. |
| `uint8_t` index limits input to 255 chars | Use `size_t` for string position/index variables in parsers |
| Whitespace handling too strict | Add a `skipWhitespace()` helper that skips spaces *and* tabs; call it before every token and after consuming delimiters |
| `0x` prefix not handled | Strip optional `0x` / `0X` prefix before parsing hex digits |
| Invalid hex chars don't stop parsing | Break the digit loop on first invalid character instead of silently accepting it |
| `value *= 16` runs on invalid chars | Only multiply and add when the character is a valid hex digit |
| Leading whitespace rejected | Skip leading whitespace *before* validating the first character |
| Parser overflows silently on too many digits | Use appropriately sized types (`uint16_t` for words, `uint8_t` for bytes) and let the type width be the natural ceiling; document if overflow is intended |
| CMake relative path `src/` breaks out-of-tree builds | Use `${CMAKE_CURRENT_SOURCE_DIR}/src` instead |

## Session References

- `references/serial-parser-extraction.md` — Concrete walkthrough of extracting a serial parser from Pico SDK-dependent firmware.
- `references/expanded-serial-parser-coverage.md` — Full 36-test suite covering all 14 buttons, HAT directions, and combinations.
- `references/host-side-sender-testing.md` — Full 54-test Rust integration suite for the host-side serial sender crate (async state machine, protocol encoders, error handling).
