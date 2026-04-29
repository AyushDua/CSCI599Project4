#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="results/run_results.csv"
PW_JSON="results/playwright_layer3.json"

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

# Build Wasm (uses whatever src/codec.c is currently in place)
"$ROOT_DIR/scripts/build_web.sh"

# B002: swap app.js *after* the Wasm build so the correct Wasm is in web/
if [[ "$BUG_ID" == "B002_CODEC" ]]; then
  echo "[test_web] Swapping web/app.js → app_B002.js"
  cp "$ROOT_DIR/web/app.js"      "$ROOT_DIR/web/app.js.bak"
  cp "$ROOT_DIR/web/app_B002.js" "$ROOT_DIR/web/app.js"
  RESTORE_APP_JS=1
fi

# Remove stale report so we don't parse an old file if Playwright crashes early
rm -f "$PW_JSON"

mkdir -p "$(dirname "$CSV")"

set +e
npx playwright test
EXIT_CODE=$?
set -e

# Always parse results (even when tests failed)
python3 "$ROOT_DIR/scripts/playwright_json_to_csv.py" "$PW_JSON" "$CSV" "$BUG_ID"

exit $EXIT_CODE
