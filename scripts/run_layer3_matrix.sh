#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_VARIANTS="CLEAN_CODEC:${ROOT_DIR}"

VARIANT_SPECS_RAW="${LAYER3_MATRIX_VARIANTS:-$DEFAULT_VARIANTS}"
# Use relative paths so Python on Windows can resolve them correctly
CSV_OUT="${LAYER3_MATRIX_CSV:-results/layer3_matrix.csv}"
RESET_CSV="${LAYER3_MATRIX_RESET_CSV:-1}"
SUMMARY_OUT="${LAYER3_SUMMARY_CSV:-results/layer3_summary.csv}"
BROWSER_SUMMARY_OUT="${LAYER3_BROWSER_SUMMARY_CSV:-results/layer3_browser_summary.csv}"

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
export PYTHON

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_layer3_matrix.sh
  ./scripts/run_layer3_matrix.sh CLEAN_CODEC:. B001_CODEC:. B002_CODEC:. B003_CODEC:.

Variant format:
  BUG_ID:/absolute/or/relative/workspace/path

Environment overrides:
  LAYER3_MATRIX_VARIANTS      Comma-separated variant specs. Default: CLEAN_CODEC:<current repo>
  LAYER3_MATRIX_CSV           Output CSV path. Default: results/layer3_matrix.csv
  LAYER3_MATRIX_RESET_CSV     Remove output CSV before running. Default: 1
  LAYER3_SUMMARY_CSV          Summary CSV path. Default: results/layer3_summary.csv
  LAYER3_BROWSER_SUMMARY_CSV  Per-browser summary CSV path. Default: results/layer3_browser_summary.csv
  LAYER3_REPEAT_RUNS          Repeat count per variant. Default: 1
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

declare -a VARIANT_SPECS=()
if [[ $# -gt 0 ]]; then
  VARIANT_SPECS=("$@")
else
  IFS=',' read -r -a VARIANT_SPECS <<< "$VARIANT_SPECS_RAW"
fi

mkdir -p "$(dirname "$CSV_OUT")"

if [[ "$RESET_CSV" == "1" ]]; then
  rm -f "$CSV_OUT"
fi

run_variant() {
  local bug_id="$1"
  local workspace_path="$2"

  echo "[Layer3 Matrix] bug_id=$bug_id workspace=$workspace_path"

  (
    cd "$workspace_path"

    set +e
    BUG_ID="$bug_id" \
    CSV="$CSV_OUT" \
    LAYER3_REPEAT_RUNS="$LAYER3_REPEAT_RUNS" \
      ./scripts/test_web.sh
    local run_rc=$?
    set -e

    if [[ $run_rc -ne 0 ]]; then
      echo "[Layer3 Matrix] bug_id=$bug_id completed_with_failures exit_code=$run_rc"
    fi

    exit 0
  )
}

for spec in "${VARIANT_SPECS[@]}"; do
  if [[ "$spec" == *:* ]]; then
    bug_id="${spec%%:*}"
    workspace_path="${spec#*:}"
  else
    bug_id="$spec"
    workspace_path="$ROOT_DIR"
  fi

  workspace_path="$(cd "$workspace_path" && pwd)"

  if [[ ! -d "$workspace_path" ]]; then
    echo "Missing workspace: $workspace_path"
    exit 2
  fi

  if [[ ! -x "$workspace_path/scripts/test_web.sh" ]]; then
    echo "Missing layer 3 harness in workspace: $workspace_path"
    exit 2
  fi

  run_variant "$bug_id" "$workspace_path"
done

echo "[Layer3 Matrix] wrote results to $CSV_OUT"

# Convert paths to Windows format for Python on Windows (Git Bash compatibility)
if command -v cygpath >/dev/null 2>&1; then
  CSV_WIN="$(cygpath -w "$CSV_OUT")"
  SUMMARY_WIN="$(cygpath -w "$SUMMARY_OUT")"
  BROWSER_WIN="$(cygpath -w "$BROWSER_SUMMARY_OUT")"
  SCRIPT_WIN="$(cygpath -w "$ROOT_DIR/scripts/analyze_layer3_results.py")"
else
  CSV_WIN="$CSV_OUT"
  SUMMARY_WIN="$SUMMARY_OUT"
  BROWSER_WIN="$BROWSER_SUMMARY_OUT"
  SCRIPT_WIN="$ROOT_DIR/scripts/analyze_layer3_results.py"
fi

"$PYTHON" "$SCRIPT_WIN" \
  "$CSV_WIN" \
  --summary-out "$SUMMARY_WIN" \
  --browser-summary-out "$BROWSER_WIN"
