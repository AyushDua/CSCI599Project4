# CSCI599 Topic 4 — WebAssembly Testing & QA (3-Layer MVP)

This repo is a **starter MVP** for the semester project on **Testing & Quality Assurance for WebAssembly**.  
It runs the *same core C module* through **three testing layers**:

1) **Layer 1 (Source-level):** native unit tests (GoogleTest)  
2) **Layer 2 (Wasm module-level):** WASI build executed in **Wasmtime**  
3) **Layer 3 (JS–Wasm integration):** browser tests via **Playwright** across Chromium/Firefox/WebKit

It also generates a unified results file: `results/run_results.csv` with per-test outcomes.

---

## Project Layout (What each folder/file is)

### Core code (shared across all layers)
- `src/codec.h`  
  Public API contract for the codec library (status codes, buffer+length style API).
- `src/codec.c`  
  Implementation of the codec logic (currently hex encoding).

### Layer 1 — Native unit tests (source-level)
- `tests/source/test_codec.cpp`  
  GoogleTest cases for `codec_hex_encode` (edge cases + “bug-catcher” tests).
- `CMakeLists.txt`  
  Builds the native library + test binary via CMake/Ninja.
- `scripts/build_native.sh`  
  Builds native binaries into `build/native/`.
- `scripts/test_native.sh`  
  Runs native tests, writes **one CSV row per test** to `results/run_results.csv` (via gtest JSON output + parser).

### Layer 2 — Wasm module tests (WASI + Wasmtime)
- `src/wasi_main.c`  
  WASI “command wrapper”: reads bytes from stdin → calls codec → prints output.
- `scripts/install_wasi_sdk.sh`  
  Installs WASI SDK toolchain into `.tools/` (repo-local so the team matches versions).
- `scripts/build_wasi.sh`  
  Compiles `codec.c + wasi_main.c` into `build/wasi/codec_wasi.wasm`.
- `scripts/test_wasi.sh`  
  Runs multiple WASI test cases via `wasmtime run` and appends results to CSV.

### Layer 3 — Browser integration tests (JS boundary)
- `src/web_api.c`  
  Emscripten-exported wrapper for JS to call (`codec_hex_encode_z`).
- `scripts/install_emsdk.sh`  
  Installs Emscripten SDK into `.tools/`.
- `scripts/build_web.sh`  
  Produces `web/codec_web.js` and `web/codec_web.wasm`.
- `web/index.html`  
  Loads the app.
- `web/app.js`  
  JS boundary logic: TextEncoder → malloc → copy into `Module.HEAPU8` → call Wasm → `UTF8ToString`.
- `playwright.config.js`  
  Playwright config: runs tests in Chromium/Firefox/WebKit and writes JSON report.
- `tests/web/codec.spec.js`  
  Playwright tests that call `window.hexEncode(...)` and assert results.

### Results / datasets / tooling
- `datasets/bugs.csv`  
  Bug metadata table (ground truth). Expand this as you add seeded bugs.
- `results/run_results.csv`  
  Unified results table across layers. One row per test case.
- `scripts/log_csv.sh`  
  CSV append helper (shared pattern).
- `scripts/gtest_json_to_csv.py`  
  Converts gtest JSON into per-test CSV rows for Layer 1.
- `scripts/playwright_json_to_csv.py`  
  Converts Playwright JSON report into per-test CSV rows for Layer 3.
- `.tools/`  
  Repo-local toolchains (WASI SDK + emsdk). **Not committed to git**.
- `scripts/all_smoke.sh`  
  Runs end-to-end: Layer1 → Layer2 → Layer3.

---

## CSV Schema (Oracle / Outcomes)

`results/run_results.csv` columns:

- `timestamp` – UTC time
- `bug_id` – label for the build/variant (default `CLEAN_CODEC`)
- `layer` – `layer1_native` | `layer2_wasmtime` | `layer3_browser`
- `runtime` – `native` | `wasmtime` | `chromium` | `firefox` | `webkit`
- `test_name` – the individual test case name
- `outcome` – `pass` | `fail` | `skip`
- `failure_kind` – one of:
  - `assertion_fail` (test assertion failed)
  - `output_mismatch` (expected != actual)
  - `trap` (Wasm trap at runtime; module-level)
  - `exception` (JS/runtime error, page.evaluate error, etc.)
  - `exit_code` (non-zero process exit; module-level)
- `details` – short error text (truncated)

### What counts as the “oracle”?
- **Layer 1:** assertions in GoogleTest (`EXPECT_EQ`, etc.)
- **Layer 2:** expected stdout vs actual OR trap/exit behavior
- **Layer 3:** Playwright assertions + JS runtime exceptions

---

## Setup (macOS)

### One-time prerequisites
1) Install Xcode CLI tools:
```bash
xcode-select --install