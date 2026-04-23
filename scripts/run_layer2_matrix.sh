#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_VARIANTS="CLEAN_CODEC:${ROOT_DIR}"

VARIANT_SPECS_RAW="${LAYER2_MATRIX_VARIANTS:-$DEFAULT_VARIANTS}"
CSV_OUT="${LAYER2_MATRIX_CSV:-$ROOT_DIR/results/layer2_matrix.csv}"
RESET_CSV="${LAYER2_MATRIX_RESET_CSV:-1}"
SUMMARY_OUT="${LAYER2_SUMMARY_CSV:-$ROOT_DIR/results/layer2_summary.csv}"
MODE_SUMMARY_OUT="${LAYER2_MODE_SUMMARY_CSV:-$ROOT_DIR/results/layer2_mode_summary.csv}"

WASI_MODE="${WASI_MODE:-full}"
WASI_EXECUTION_MODE="${WASI_EXECUTION_MODE:-both}"
WASI_REPEAT_RUNS="${WASI_REPEAT_RUNS:-5}"
WASI_RANDOM_CASES="${WASI_RANDOM_CASES:-}"
WASI_MAX_RANDOM_LEN="${WASI_MAX_RANDOM_LEN:-}"
WASI_RANDOM_SEED="${WASI_RANDOM_SEED:-5994}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_layer2_matrix.sh
  ./scripts/run_layer2_matrix.sh CLEAN_CODEC:. B001_CODEC:../bug-b001 B003_CODEC:../bug-b003

Variant format:
  BUG_ID:/absolute/or/relative/workspace/path

Environment overrides:
  LAYER2_MATRIX_VARIANTS    Comma-separated variant specs. Default: CLEAN_CODEC:<current repo>
  LAYER2_MATRIX_CSV         Output CSV path. Default: results/layer2_matrix.csv
  LAYER2_MATRIX_RESET_CSV   Remove output CSV before running. Default: 1
  LAYER2_SUMMARY_CSV        Summary CSV path. Default: results/layer2_summary.csv
  LAYER2_MODE_SUMMARY_CSV   Per-mode summary CSV path. Default: results/layer2_mode_summary.csv
  WASI_MODE                 fast or full. Default: full
  WASI_EXECUTION_MODE       start, invoke, or both. Default: both
  WASI_REPEAT_RUNS          Repeat count per variant. Default: 5
  WASI_RANDOM_CASES         Override random case count passed to test_wasi.sh
  WASI_MAX_RANDOM_LEN       Override max random input length passed to test_wasi.sh
  WASI_RANDOM_SEED          Random seed passed to test_wasi.sh. Default: 5994
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

if [[ "$RESET_CSV" == "1" ]]; then
  rm -f "$CSV_OUT"
fi

mkdir -p "$(dirname "$CSV_OUT")"
CSV_OUT="$(cd "$(dirname "$CSV_OUT")" && pwd)/$(basename "$CSV_OUT")"

run_variant() {
  local bug_id="$1"
  local workspace_path="$2"
  local run_rc=0

  echo "[Layer2 Matrix] bug_id=$bug_id workspace=$workspace_path"

  (
    cd "$workspace_path"
    BUG_ID="$bug_id" ./scripts/build_wasi.sh

    if [[ -n "$WASI_RANDOM_CASES" ]]; then
      export WASI_RANDOM_CASES
    fi
    if [[ -n "$WASI_MAX_RANDOM_LEN" ]]; then
      export WASI_MAX_RANDOM_LEN
    fi

    set +e
    BUG_ID="$bug_id" \
    CSV="$CSV_OUT" \
    WASI_MODE="$WASI_MODE" \
    WASI_EXECUTION_MODE="$WASI_EXECUTION_MODE" \
    WASI_REPEAT_RUNS="$WASI_REPEAT_RUNS" \
    WASI_RANDOM_SEED="$WASI_RANDOM_SEED" \
      ./scripts/test_wasi.sh
    run_rc=$?
    set -e

    if [[ $run_rc -ne 0 ]]; then
      echo "[Layer2 Matrix] bug_id=$bug_id completed_with_failures exit_code=$run_rc"
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

  if [[ ! -x "$workspace_path/scripts/test_wasi.sh" ]]; then
    echo "Missing layer 2 harness in workspace: $workspace_path"
    exit 2
  fi

  run_variant "$bug_id" "$workspace_path"
done

echo "[Layer2 Matrix] wrote results to $CSV_OUT"

python3 "$ROOT_DIR/scripts/analyze_layer2_results.py" \
  "$CSV_OUT" \
  --summary-out "$SUMMARY_OUT" \
  --mode-summary-out "$MODE_SUMMARY_OUT"