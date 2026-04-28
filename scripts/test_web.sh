#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="${CSV:-results/run_results.csv}"
PW_JSON="results/playwright_layer3.json"
LAYER3_REPEAT_RUNS="${LAYER3_REPEAT_RUNS:-1}"

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

CSV_WIN="$(to_win_path "$CSV")"
PW_JSON_WIN="$(to_win_path "$PW_JSON")"

# Build once before repeat runs
BUG_ID="$BUG_ID" ./scripts/build_web.sh

FAIL=0

for ((run_index=1; run_index<=LAYER3_REPEAT_RUNS; run_index++)); do
  rm -f "$PW_JSON"

  set +e
  npx playwright test
  EXIT_CODE=$?
  set -e

  "$PYTHON" scripts/playwright_json_to_csv.py "$PW_JSON_WIN" "$CSV_WIN" "$BUG_ID" "$run_index"

  if [[ $EXIT_CODE -ne 0 ]]; then
    FAIL=1
  fi
done

echo "[Layer3 Summary] bug_id=$BUG_ID repeats=$LAYER3_REPEAT_RUNS"

exit $FAIL
