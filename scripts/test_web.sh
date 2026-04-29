#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="${CSV:-results/run_results.csv}"
PW_JSON="results/playwright_layer3.json"
LAYER3_REPEAT_RUNS="${LAYER3_REPEAT_RUNS:-1}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ---------------------------------------------------------------------------
# Bug-injection helpers
# Swap buggy source files in before building / serving, then restore on exit.
# ---------------------------------------------------------------------------
RESTORE_CODEC_C=0
RESTORE_APP_JS=0

cleanup() {
  if [[ $RESTORE_CODEC_C -eq 1 ]]; then
    cp "$ROOT_DIR/src/codec.c.bak" "$ROOT_DIR/src/codec.c"
    rm -f "$ROOT_DIR/src/codec.c.bak"
    echo "[test_web] Restored src/codec.c"
  fi
  if [[ $RESTORE_APP_JS -eq 1 ]]; then
    cp "$ROOT_DIR/web/app.js.bak" "$ROOT_DIR/web/app.js"
    rm -f "$ROOT_DIR/web/app.js.bak"
    echo "[test_web] Restored web/app.js"
  fi
}
trap cleanup EXIT

case "$BUG_ID" in
  B001_CODEC)
    echo "[test_web] Injecting B001 — off-by-one in codec.c encode loop"
    cp "$ROOT_DIR/src/codec.c"      "$ROOT_DIR/src/codec.c.bak"
    cp "$ROOT_DIR/src/codec_B001.c" "$ROOT_DIR/src/codec.c"
    RESTORE_CODEC_C=1
    ;;
  B002_CODEC)
    # Wasm does not need recompiling for B002; only app.js changes.
    # We still call build_web.sh below to ensure the Wasm is present and up-to-date.
    echo "[test_web] B002 selected — will swap app.js after Wasm build"
    ;;
  B003_CODEC)
    echo "[test_web] Injecting B003 — output size guard removed from codec.c"
    cp "$ROOT_DIR/src/codec.c"      "$ROOT_DIR/src/codec.c.bak"
    cp "$ROOT_DIR/src/codec_B003.c" "$ROOT_DIR/src/codec.c"
    RESTORE_CODEC_C=1
    ;;
  CLEAN_CODEC)
    echo "[test_web] Running clean (no bug injected)"
    ;;
  *)
    echo "[test_web] WARNING: unknown BUG_ID '$BUG_ID' — running clean build"
    ;;
esac

# Detect python command; verify it actually runs (Windows Store stub reports as found but exits 49)
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if command -v python >/dev/null 2>&1 && python -c "" >/dev/null 2>&1; then
    PYTHON="python"
  elif command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
    PYTHON="python3"
  else
    echo "python not found on PATH"
    exit 2
  fi
fi

# Convert paths to Windows format for Python on Windows (Git Bash compatibility)
to_win_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    echo "$1"
  fi
}

# Build Wasm (uses whatever src/codec.c is currently in place)
"$ROOT_DIR/scripts/build_web.sh"

# B002: swap app.js *after* the Wasm build so the correct Wasm is in web/
if [[ "$BUG_ID" == "B002_CODEC" ]]; then
  echo "[test_web] Swapping web/app.js → app_B002.js"
  cp "$ROOT_DIR/web/app.js"      "$ROOT_DIR/web/app.js.bak"
  cp "$ROOT_DIR/web/app_B002.js" "$ROOT_DIR/web/app.js"
  RESTORE_APP_JS=1
fi

CSV_WIN="$(to_win_path "$CSV")"
PW_JSON_WIN="$(to_win_path "$PW_JSON")"

mkdir -p "$(dirname "$CSV")"

FAIL=0

for ((run_index=1; run_index<=LAYER3_REPEAT_RUNS; run_index++)); do
  rm -f "$PW_JSON"

  set +e
  npx playwright test
  EXIT_CODE=$?
  set -e

  "$PYTHON" "$ROOT_DIR/scripts/playwright_json_to_csv.py" "$PW_JSON_WIN" "$CSV_WIN" "$BUG_ID" "$run_index"

  if [[ $EXIT_CODE -ne 0 ]]; then
    FAIL=1
  fi
done

echo "[Layer3 Summary] bug_id=$BUG_ID repeats=$LAYER3_REPEAT_RUNS"

exit $FAIL
