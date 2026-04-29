# CSCI599 Topic 4 — WebAssembly Testing & QA (3-Layer MVP)

This repo is a **starter MVP** for the semester project on **Testing & Quality Assurance for WebAssembly**.  
It runs the _same core C module_ through **three testing layers**:

1. **Layer 1 (Source-level):** native unit tests (GoogleTest)
2. **Layer 2 (Wasm module-level):** WASI build executed in **Wasmtime**
3. **Layer 3 (JS–Wasm integration):** browser tests via **Playwright** across Chromium/Firefox/WebKit

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
    Layer 2 pipeline runner: compiles the case generator, loads tests from `tests/integrations/`, executes them with `wasmtime run`, and appends results to CSV.

#### Layer 2 execution modes

- CLI / `_start` mode: pipes raw bytes into the WASI command module and checks stdout against the oracle.
- Exported `--invoke` mode: calls the exported `codec_wasi_invoke_case` function for built-in oracle cases.
- Stability runs: set `WASI_REPEAT_RUNS=N` to repeat the full Layer 2 matrix and check for flaky behavior.

Example commands:

```bash
./scripts/build_wasi.sh
./scripts/test_wasi.sh
WASI_EXECUTION_MODE=invoke ./scripts/test_wasi.sh
WASI_EXECUTION_MODE=both WASI_REPEAT_RUNS=5 ./scripts/test_wasi.sh
```

#### Layer 2 matrix + visual outputs

Run the basic Layer 2 experiment matrix across the clean baseline and two seeded bug variants:

```bash
WASI_MODE=fast WASI_REPEAT_RUNS=1 ./scripts/run_layer2_matrix.sh CLEAN_CODEC:. B001_CODEC:. B003_CODEC:.
```

This updates:

- `results/layer2_matrix.csv`
- `results/layer2_summary.csv`
- `results/layer2_mode_summary.csv`
- `results/layer2_master_matrix.csv`
- `results/layer2_relationship_matrix.csv`
- `results/layer2_chart.svg`

To regenerate the Layer 2 analysis outputs from an existing matrix
This generates the summary bar chart:

```bash
./scripts/analyze_layer2_results.py results/layer2_matrix.csv
```

If you want to regenerate analysis files without auto-opening the chart
This generates the more visual matrix view:

```bash
./scripts/analyze_layer2_results.py results/layer2_matrix.csv --no-open-chart
./scripts/render_layer2_chart.py
```

Main visual files:

- `results/layer2_chart.svg`
- `results/layer2_visual_matrix.svg`

### Layer 3 — Browser integration tests (JS boundary)

- `src/web_api.c`  
  Emscripten-exported wrapper for JS to call (`codec_hex_encode_z`).
- `scripts/install_emsdk.sh`  
  Installs Emscripten SDK into `.tools/`.
- `scripts/build_web.sh`  
  Produces `web/codec_web.js` and `web/codec_web.wasm`. Also writes `web/app.js` from an embedded template (so edits to `app.js` directly will be overwritten on the next build — edit the template in this script instead).
- `web/index.html`  
  Loads the app.
- `web/app.js`  
  JS boundary logic: TextEncoder → malloc → copy into `Module.HEAPU8` → call Wasm → `UTF8ToString`. Also exposes `window._Module` so Playwright tests can call `_codec_hex_encode_z` directly for boundary and trap testing.
- `playwright.config.js`  
  Playwright config: runs tests in Chromium/Firefox/WebKit, writes JSON report to `results/playwright_layer3.json`, and generates an HTML report in `playwright-report/`.
- `tests/web/codec.spec.js`  
  37 Playwright test cases (111 total runs across 3 browsers). Covers happy-path encoding, B001/B002/B003 detectors, raw-byte boundary calls via `window._Module`, randomised large-input stress tests, and cross-browser surrogate pair checks.

#### Layer 3 bug variants

The test harness injects bugs by swapping source files before building, then restoring them on exit (via `trap cleanup EXIT`):

- `src/codec_B001.c` — off-by-one loop bug: skips the last byte of any input.
- `src/codec_B003.c` — output-size guard removed: undersized buffer causes a Wasm memory trap.
- `web/app_B002.js` — wrong JS length arg: passes `str.length` instead of `bytes.length`, silently truncates multi-byte UTF-8 characters.

#### Layer 3 matrix + visual outputs

Run all four variants (clean baseline + 3 bug variants) across all three browsers:

```bash
./scripts/run_layer3_matrix.sh CLEAN_CODEC:. B001_CODEC:. B002_CODEC:. B003_CODEC:.
```

This updates:

- `results/layer3_matrix.csv`
- `results/layer3_summary.csv`
- `results/layer3_browser_summary.csv`
- `results/layer3_master_matrix.csv`
- `results/layer3_relationship_matrix.csv`
- `results/layer3_chart.html`
- `results/layer3_chart.svg`
- `results/layer3_visual_matrix.svg`

To regenerate charts from an existing matrix without re-running tests:

```bash
python3 scripts/analyze_layer3_results.py results/layer3_matrix.csv
python3 scripts/render_layer3_chart.py
```

Main visual files:

- `results/layer3_chart.html` — interactive HTML matrix (open in browser)
- `results/layer3_visual_matrix.svg` — static SVG matrix view

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

1. Install Xcode CLI tools:

```bash
xcode-select --install
```
