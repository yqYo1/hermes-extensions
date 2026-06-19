---
name: rust-development
description: "Rust application development: build-time code generation, crate consolidation, FFmpeg video encoding, VAAPI hardware acceleration, WebRTC streaming, and nix integration."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [rust, cargo, build-script, code-generation, ffmpeg, video-encoding, vaapi, webrtc, tauri, nix]
    related_skills: [nix-flake-devops, writing-plans]
---

# Rust Development

Comprehensive guidance for Rust application development covering build-time code generation, project structure (crate consolidation), video encoding with FFmpeg/VAAPI, WebRTC streaming integration, and nix flake packaging.

---

## Section 1: Build-Time Code Generation

Use Cargo `build.rs` to parse Rust source files and generate derived artifacts (type definitions, bindings, documentation) at compile time. This ensures generated code stays synchronized with the source API.

### When to Use

- **Language bindings**: Generate Lua `.d.lua`, TypeScript `.d.ts`, or Python stub files from Rust `pub fn` signatures
- **API documentation**: Extract doc comments to produce external docs
- **Schema generation**: Derive OpenAPI/GraphQL schemas from handler functions
- **FFI glue**: Generate C header files from `extern "C"` functions

### When NOT to Use

- Simple cases where proc macros suffice (`derive` attributes)
- One-off generation that doesn't need recompilation triggers
- Cases where `syn` + proc macro would be cleaner

### Implementation Pattern

```rust
// build.rs
use std::fs;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=src/api.rs");
    println!("cargo:rerun-if-changed=build.rs");

    let manifest_dir = PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").unwrap()
    );
    let out_dir = PathBuf::from(
        std::env::var_os("OUT_DIR").unwrap()
    );

    let source = fs::read_to_string(manifest_dir.join("src/api.rs"))
        .expect("Failed to read source");

    let generated = generate_types(&source);
    let out_path = out_dir.join("generated.d.lua");
    fs::write(&out_path, generated)
        .expect("Failed to write generated file");
}
```

**Critical**: Only write to `OUT_DIR`. Never write to the source tree.

### Source Parsing Strategy

#### Option A: Ad-hoc String Parsing (Simple APIs)

For simple patterns like `api.set("name", lua.create_function(|_, (args): (Types)| { ... }))`:

```rust
fn extract_function_signature(line: &str) -> Option<(String, Vec<(String, String)>)> {
    let params_start = line.find("|_, ").or_else(|| line.find("|lua, "))?;
    // ... parse names and types
}
```

**Pitfalls**: Multi-line closures break parsing; comments with quotes cause false positives; `rustfmt` changes spacing.

**Mitigations**: Skip comment-only lines; handle both `| {` and `|{` patterns; use `strip_prefix` instead of `starts_with` + slicing.

#### Option B: syn Crate (Complex APIs)

```toml
[build-dependencies]
syn = { version = "2", features = ["full", "parsing"] }
quote = "1"
```

**Trade-off**: `syn` adds ~2s to build time but handles all edge cases.

### Type Mapping

| Rust Type | Lua | TypeScript | Python |
|-----------|-----|------------|--------|
| `u64`, `i32` | `integer` | `number` | `int` |
| `f64` | `number` | `number` | `float` |
| `String`, `&str` | `string` | `string` | `str` |
| `bool` | `boolean` | `boolean` | `bool` |
| `Vec<T>` | `T[]` | `T[]` | `list[T]` |
| `Option<T>` | `T?` | `T \| undefined` | `Optional[T]` |
| `Result<T, E>` | `T` (or panic) | `T` (throws) | `T` (raises) |

### Error Handling & Validation

```rust
if functions.is_empty() {
    println!("cargo:warning=Type generation: parser failed, using static fallback");
}
const EXPECTED_COUNT: usize = 18;
if functions.len() < EXPECTED_COUNT {
    println!("cargo:warning=Type generation: parsed {} of {} expected functions",
        functions.len(), EXPECTED_COUNT);
}
```

### Testing

Build script tests go in `#[cfg(test)]` module within `build.rs`. Note: `cargo test` doesn't run `build.rs` tests by default.

### References

- `references/lua-type-generation-example.md` — Full EmmyLua type generation from mlua API bindings
- `references/tauri-dev-nix-setup.md` — `nix run .#tauri-dev` after crate consolidation

---

## Section 2: Crate Consolidation

When a project has many small Rust crates that are NOT intended to be published as standalone libraries, consolidate them into a single crate with feature flags.

### Before (8 crates)
```
rust/
├── pokecon-events/
├── pokecon-serial/
├── pokecon-cv/
├── pokecon-core/
├── pokecon-notify/
├── pokecon-net/
├── pokecon-lua/
└── pokecon-pybindings/  (cdylib — must remain separate)
```

### After (2 crates)
```
rust/
├── pokecon-core/        # All rlib crates merged
│   ├── src/events/
│   ├── src/serial/
│   ├── src/cv/
│   ├── src/notify/
│   ├── src/net/
│   ├── src/lua/
│   └── src/{command_manager,profile,settings}.rs
└── pokecon-pybindings/  # cdylib — separate
```

### Feature flags design
```toml
[features]
default = []
v4l = ["dep:v4l", "dep:jpeg-decoder"]
notify = ["dep:reqwest", "dep:notify-rust"]
mqtt = ["dep:rumqttc", "dep:bytes"]
lua = ["dep:mlua"]
```

### Migration steps
1. Copy all source files into subdirectories of the unified crate
2. Rename `lib.rs` to `mod.rs` in each subdirectory
3. Update all `use crate::` references to include the new module path
4. Update workspace `Cargo.toml` members list
5. Update dependent crates' `Cargo.toml` to use the unified crate with features
6. Remove old crate directories

### Pitfalls
- **Doc-test imports**: Update doc comments that use old crate names
- **Bench files**: Move bench files into the unified crate or remove them
- **Dev-dependencies**: Consolidate dev-dependencies
- **Duplicate mod error**: If both `events.rs` and `events/mod.rs` exist, Rust errors. Remove the `.rs` file.
- **Crate consolidation orphans**: After merging crates, update ALL consumers (workspace members, consumer `Cargo.toml`, consumer source files, feature flags, Tauri config, nix flake)

### When to consolidate
- ✅ All crates are internal-only (not published to crates.io)
- ✅ Crates have tight coupling (many cross-dependencies)
- ✅ You want simpler dependency management or feature flags for optional components

### When NOT to consolidate
- ❌ Crates are published as standalone libraries
- ❌ Crates need different edition/rust-version requirements
- ❌ Crates have fundamentally different build requirements (e.g., `cdylib` vs `rlib`)

### References

- `references/crate-consolidation-pattern.md` — Detailed migration guide with before/after structure

---

## Section 3: FFmpeg Video Encoding

Encode video in Rust using FFmpeg libraries. Covers both software encoding (libx264, libsvtav1) and hardware-accelerated encoding (VAAPI on Linux).

### Crate Selection

| Crate | Downloads/mo | Maintenance | VAAPI | Level | Notes |
|-------|-------------|-------------|-------|-------|-------|
| **ffmpeg-next** | ~727k | Maintenance mode | ⚠️ Partial | Low | Most popular. Safe wrapper. VAAPI hwcontext APIs NOT fully wrapped. |
| **ez-ffmpeg** | Low | Active (2026-02) | ✅ `hwaccel` module | High | Easier API but FFmpeg 7.0+ required. Less battle-tested. |

**Recommendation**: Use `ffmpeg-next` for broad compatibility, but be aware hardware encoding requires falling back to raw `ffmpeg-sys` calls.

### Software Encoding (H.264 via libx264)

```rust
use ffmpeg_next::{
    codec::{self, Context, Id},
    format::Pixel,
    Dictionary,
};

fn create_software_h264_encoder(width: u32, height: u32, fps: u32, bitrate_kbps: u32)
    -> Result<ffmpeg::codec::encoder::video::Encoder, String> {
    ffmpeg_next::init().map_err(|e| format!("FFmpeg init failed: {}", e))?;
    let codec = codec::encoder::find(Id::H264)
        .ok_or("H.264 encoder not found")?;
    let mut context = Context::new();
    let mut encoder = context.encoder().video()
        .map_err(|e| format!("Encoder context failed: {}", e))?;
    encoder.set_width(width);
    encoder.set_height(height);
    encoder.set_time_base(ffmpeg_next::Rational::new(1, fps as i32));
    encoder.set_bit_rate((bitrate_kbps * 1000) as usize);
    encoder.set_format(Pixel::YUV420P);
    let mut opts = Dictionary::new();
    opts.set("preset", "medium");
    opts.set("tune", "zerolatency");
    opts.set("profile", "main");
    encoder.open_as_with(codec, opts)
        .map_err(|e| format!("Failed to open encoder: {}", e))
}
```

### VAAPI Hardware Encoding (Linux)

**Critical Pitfall**: `ffmpeg-next` does NOT wrap `AVHWDeviceContext` management. You must use `ffmpeg-sys` raw FFI for `av_hwdevice_ctx_create` and related APIs.

#### Working ffmpeg-next + ffmpeg-sys VAAPI Pattern (ffmpeg-next 8.1)

```rust
use std::ptr::{self, NonNull};
use ffmpeg_next as ffmpeg;
use ffmpeg_sys_next as sys;

pub struct VaapiDeviceContext {
    ptr: NonNull<sys::AVBufferRef>,
}

unsafe impl Send for VaapiDeviceContext {}
unsafe impl Sync for VaapiDeviceContext {}

impl VaapiDeviceContext {
    pub fn new(device_path: &str) -> Result<Self, String> {
        ffmpeg::init().map_err(|e| format!("FFmpeg init failed: {}", e))?;
        let device_cstr = std::ffi::CString::new(device_path)
            .map_err(|e| format!("Invalid device path: {}", e))?;
        let mut hw_device_ctx: *mut sys::AVBufferRef = ptr::null_mut();
        let ret = unsafe {
            sys::av_hwdevice_ctx_create(
                &mut hw_device_ctx,
                sys::AVHWDeviceType::AV_HWDEVICE_TYPE_VAAPI,
                device_cstr.as_ptr(),
                ptr::null_mut(),
                0,
            )
        };
        if ret < 0 || hw_device_ctx.is_null() {
            return Err(format!("av_hwdevice_ctx_create failed: {}", ret));
        }
        Ok(Self { ptr: unsafe { NonNull::new_unchecked(hw_device_ctx) } })
    }
    pub unsafe fn as_ptr(&self) -> *mut sys::AVBufferRef { self.ptr.as_ptr() }
}

impl Drop for VaapiDeviceContext {
    fn drop(&mut self) {
        unsafe {
            let mut ptr = self.ptr.as_ptr();
            sys::av_buffer_unref(&mut ptr);
        }
    }
}
```

#### Critical ffmpeg-next 8.1 API Details

- `receive_packet()` returns `Result<(), Error>`, not `Option`
- `Encoder::video()` returns `Result<Video, Error>`
- `av_buffer_ref` NULL check is mandatory — it can fail on OOM
- `av_buffer_unref` requires a mutable pointer to the pointer: `let mut ptr = self.ptr.as_ptr(); sys::av_buffer_unref(&mut ptr);`

### Pixel Format Conversion (RGB24 → YUV420P)

```rust
use ffmpeg_next::{
    format::Pixel,
    frame::Video,
    software::scaling::{context::Context as ScaleContext, flag::Flags},
};

fn rgb_to_yuv420(width: u32, height: u32, rgb: &[u8]) -> Result<Video, String> {
    let mut scaler = ScaleContext::get(
        Pixel::RGB24, width, height,
        Pixel::YUV420P, width, height,
        Flags::BILINEAR,
    ).map_err(|e| format!("Scaler creation failed: {}", e))?;
    let mut input = Video::new(Pixel::RGB24, width, height);
    input.data_mut(0).copy_from_slice(rgb);
    let mut output = Video::new(Pixel::YUV420P, width, height);
    scaler.run(&input, &mut output)
        .map_err(|e| format!("Scale failed: {}", e))?;
    Ok(output)
}
```

**Performance note**: Create `ScaleContext` once and reuse it. Recreating per-frame is expensive (~5-10ms for 1080p).

### WebRTC Integration with str0m

#### Codec Configuration

```rust
use str0m::RtcConfig;
use std::time::Instant;

let mut config = RtcConfig::new()
    .clear_codecs()
    .enable_h264(true)
    .enable_h265(true);
let mut rtc = config.build(Instant::now());
```

**Critical**: `Rtc::new()` uses default codecs including VP8. If the browser offers only VP8, str0m accepts it but your encoder only produces H.264, resulting in silent video failure. Always use `RtcConfig` to restrict codecs.

#### RTP Timestamp Calculation

Use the encoder's configured framerate, not a hardcoded value:

```rust
let rtp_increment = 90_000 / encoder_framerate;  // CORRECT
```

#### Annex B Compatibility with str0m

str0m's H.264 and H.265 packetizers **correctly parse Annex B bytestreams** (with `00 00 00 01` start codes). They strip AUD (type 9) and filler (type 12) NALUs, cache SPS/PPS and emit as STAP-A (H.264) or AP (H.265).

**No conversion to MP4/AVCC format is needed** before passing to str0m. Pass raw encoder output directly.

### Nix Integration

#### Optional Feature Pattern (No Version Pinning)

When using ffmpeg-next as an **optional Cargo feature** (e.g., `vaapi = ["dep:ffmpeg-next", "dep:ffmpeg-sys-next"]`), add FFmpeg to the nix devShell but NOT to the default package build:

```nix
devShells.default = pkgs.mkShell {
  buildInputs = with pkgs; [
    libva
    libva-utils
    ffmpeg  # for ffmpeg-next build-time headers
  ];
};
```

#### Decision: libva Pin vs ffmpeg-next + unsafe

| Factor | libva 2.22.0 Pin | ffmpeg-next + unsafe |
|--------|-----------------|---------------------|
| nixpkgs updates | ❌ Pinned | ✅ Latest |
| Security patches | ❌ Manual | ✅ Automatic via nixpkgs |
| Other package conflicts | ❌ libva dependents also pinned | ✅ No issues |
| Implementation complexity | ✅ Safe API | ⚠️ ~10 lines of unsafe |
| Long-term debt | ❌ Unsustainable | ✅ Sustainable |
| Codec variety | ⚠️ Limited | ✅ Full FFmpeg |

**Conclusion**: For long-term maintainability, prefer **ffmpeg-next + unsafe**. The unsafe surface is small (~10 lines) and well-isolated.

### Alternative: cros-libva (ChromeOS libva Bindings)

For direct VAAPI access without FFmpeg overhead, `cros-libva` provides safe Rust bindings to `libva`.

**Critical**: cros-libva 0.0.13 targets **libva 2.22.0**. Using libva 2.23.0+ causes compile errors due to new struct fields (e.g., `seg_id_block_size` in VP9 structs).

**Send Safety**: NONE of the cros-libva types implement `Send`. Use single-threaded execution or re-create per-thread.

### Pitfalls

1. **ffmpeg-next init() race condition**: Call once at app startup, not per-encoder.
2. **VAAPI without hwcontext**: Passing `vaapi_device` as a codec option is NOT sufficient.
3. **EAGAIN handling**: `receive_packet()` returning EAGAIN means "need more input", NOT "error".
4. **Rate control conflicts**: `rc_mode=VBR` + `qp=23` are contradictory.
5. **NV12 vs YUV420P**: NV12 is semi-planar; VAAPI prefers NV12. Requires even width/height.
6. **Encoder flushing**: Call `send_frame(None)` then drain `receive_packet()` until EAGAIN on shutdown.
7. **Hardware context lifetime**: The `AVHWDeviceContext` must outlive the encoder. Store it in the encoder struct.
8. **ScaleContext !Send**: `ffmpeg-next`'s `ScaleContext` does NOT implement `Send`.

### References

- `references/ffmpeg-next-vaapi-complete-example.rs` — Complete working VAAPI encoder with ffmpeg-next 8.1
- `references/vaapi-encoder-pitfalls.md` — NV12 frame copy, av_buffer_ref leak, Drop safety, str0m integration
- `references/cros-libva-api-coverage.md` — cros-libva API reference, version compatibility, decision matrix
- `references/annex-b-to-mp4.md` — NAL unit conversion for WebRTC (legacy; str0m accepts Annex B directly)
- `references/vaapi-ffmpeg-sys-example.md` — Complete VAAPI setup using raw FFI

---

## Section 4: Tauri Dev Environment in Nix Flakes

Configuring `nix run .#tauri-dev` after crate consolidation or frontend changes.

### tauri.conf.json

```json
{
  "build": {
    "frontendDist": "../web/dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "cd ../web && npm run dev",
    "beforeBuildCommand": "cd ../web && npm run build"
  }
}
```

**Critical**: `beforeDevCommand` must be set. Empty string = no frontend server = 404 error.

### flake.nix — runtimeInputs and targetPkgs

```nix
tauriDevScript = pkgs.writeShellApplication {
  name = "tauri-dev-script";
  runtimeInputs = [
    rustEnv
    pkgs.cargo-tauri
    pkgs.pkg-config
    pkgs.libclang
    pkgs.nodejs        # ← REQUIRED for beforeDevCommand
    pkgs.glib
    pkgs.gtk3
    # ... other GTK/WebKit deps
  ];
  text = ''
    export LIBCLANG_PATH="${pkgs.libclang.lib}/lib"
    workdir="$(mktemp -d)"
    trap 'rm -rf "$workdir"' EXIT
    cp -r "${self}/." "$workdir/"
    chmod -R +w "$workdir"
    cd "$workdir/src-tauri"
    exec cargo tauri dev
  '';
};
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `failed to read /tmp/.../pokecon-cv/Cargo.toml` | Consumer still references deleted crate | Update consumer `Cargo.toml` |
| `cannot find crate pokecon_events` | Import not updated | Change `use pokecon_events::` → `use pokecon_core::events::` |
| `cannot find notify in pokecon_core` | Feature not enabled | Add `notify = ["pokecon-core/notify"]` to consumer features |
| 404 on `http://localhost:5173` | `beforeDevCommand` empty | Set `"beforeDevCommand": "cd ../web && npm run dev"` |
| `npm: command not found` | `nodejs` missing from nix env | Add `pkgs.nodejs` to both `runtimeInputs` and `targetPkgs` |

### References

- `references/tauri-dev-nix-setup.md` — Full nix flake configuration for Tauri dev
