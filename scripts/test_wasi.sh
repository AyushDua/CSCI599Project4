#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="${CSV:-results/run_results.csv}"
WASM="build/wasi/codec_wasi.wasm"
WASI_MODE="${WASI_MODE:-full}"   # fast or full
WASI_EXECUTION_MODE="${WASI_EXECUTION_MODE:-both}"   # start, invoke, or both
WASI_REPEAT_RUNS="${WASI_REPEAT_RUNS:-1}"

# Coverage knobs (override per run as needed).
if [[ "$WASI_MODE" == "full" ]]; then
  WASI_RANDOM_CASES="${WASI_RANDOM_CASES:-100}"
  WASI_MAX_RANDOM_LEN="${WASI_MAX_RANDOM_LEN:-2048}"
else
  WASI_RANDOM_CASES="${WASI_RANDOM_CASES:-20}"
  WASI_MAX_RANDOM_LEN="${WASI_MAX_RANDOM_LEN:-256}"
fi
WASI_RANDOM_SEED="${WASI_RANDOM_SEED:-5994}"

FAIL=0
PASS_COUNT=0
FAIL_OUTPUT_MISMATCH=0
FAIL_TRAP=0
FAIL_EXIT_CODE=0
FAIL_EXCEPTION=0
WASMTIME_BIN=""

declare -a INVOKE_CASE_NAMES=(
  "invoke_empty"
  "invoke_hi"
  "invoke_ABC"
  "invoke_mixed_0001027f80ff"
  "invoke_byte_ramp_256"
)

if [[ ! -f "$WASM" ]]; then
  echo "Missing Wasm artifact: $WASM"
  echo "Run scripts/build_wasi.sh first."
  exit 2
fi

if command -v wasmtime >/dev/null 2>&1; then
  WASMTIME_BIN="$(command -v wasmtime)"
elif command -v wasmtime.exe >/dev/null 2>&1; then
  WASMTIME_BIN="$(command -v wasmtime.exe)"
elif [[ -x "$HOME/.wasmtime/bin/wasmtime" ]]; then
  WASMTIME_BIN="$HOME/.wasmtime/bin/wasmtime"
else
  echo "wasmtime not found on PATH"
  echo "Install with: curl https://wasmtime.dev/install.sh -sSf | bash"
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH"
  exit 2
fi

CASE_SOURCE="tests/integrations/layer2_wasi_cases.cpp"
CASE_BIN="build/host/layer2_wasi_cases"

if [[ ! -f "$CASE_SOURCE" ]]; then
  echo "Missing Layer 2 test definitions: $CASE_SOURCE"
  exit 2
fi

build_case_generator () {
  local compiler=""

  if command -v c++ >/dev/null 2>&1; then
    compiler="$(command -v c++)"
  elif command -v g++ >/dev/null 2>&1; then
    compiler="$(command -v g++)"
  elif command -v clang++ >/dev/null 2>&1; then
    compiler="$(command -v clang++)"
  else
    echo "No C++ compiler found for Layer 2 case generator"
    exit 2
  fi

  mkdir -p "$(dirname "$CASE_BIN")"
  "$compiler" -std=c++17 -O2 "$CASE_SOURCE" -o "$CASE_BIN"
}

if [[ ! -x "$CASE_BIN" || "$CASE_SOURCE" -nt "$CASE_BIN" ]]; then
  build_case_generator
fi

preview_hex () {
  local hex="$1"
  local max_chars=32
  if [[ ${#hex} -le $max_chars ]]; then
    echo "$hex"
  else
    echo "${hex:0:$max_chars}..."
  fi
}

classify_runtime_failure_kind () {
  local err_lower="$1"
  if [[ "$err_lower" == *"wasm trap:"* ]] || [[ "$err_lower" == *"trap"* ]]; then
    echo "trap"
  elif [[ "$err_lower" == *"timeout"* ]] || [[ "$err_lower" == *"error"* ]] || [[ "$err_lower" == *"exception"* ]]; then
    echo "exception"
  else
    echo "exit_code"
  fi
}

update_fail_counter () {
  local kind="$1"
  case "$kind" in
    output_mismatch) FAIL_OUTPUT_MISMATCH=$((FAIL_OUTPUT_MISMATCH + 1));;
    trap)            FAIL_TRAP=$((FAIL_TRAP + 1));;
    exit_code)       FAIL_EXIT_CODE=$((FAIL_EXIT_CODE + 1));;
    exception)       FAIL_EXCEPTION=$((FAIL_EXCEPTION + 1));;
  esac
}

run_case_hex () {
  local name="$1"
  local input_hex="$2"
  local run_index="$3"

  local test_name="$name"
  if [[ "$WASI_REPEAT_RUNS" != "1" ]]; then
    test_name="${name}#run${run_index}"
  fi

  local normalized_hex
  normalized_hex="$(echo "$input_hex" | tr 'A-F' 'a-f')"

  local expected="$normalized_hex"
  local input_len=$(( ${#normalized_hex} / 2 ))
  local expected_len=${#expected}
  local preview
  preview="$(preview_hex "$normalized_hex")"

  local out err rc
  local errfile
  errfile="$(mktemp -t wasi_err.XXXXXX)"

  # Capture output + exit code safely even under set -e
  set +e
  out="$(python3 - "$normalized_hex" <<'PY' | "$WASMTIME_BIN" run "$WASM" 2> "$errfile" | tr -d '\r\n'
import binascii
import sys

h = sys.argv[1]
if h:
    sys.stdout.buffer.write(binascii.unhexlify(h))
PY
)"
  rc=$?
  set -e

  err="$(cat "$errfile")"
  rm -f "$errfile"

  if [[ $rc -ne 0 ]]; then
    local kind
    kind="$(classify_runtime_failure_kind "$(echo "$err" | tr '[:upper:]' '[:lower:]')")"
    update_fail_counter "$kind"
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "fail" "$kind" "mode=start run_index=$run_index input_len=$input_len expected_len=$expected_len hex_preview=$preview rc=$rc err=$err"
    FAIL=1
    return
  fi

  if [[ "$out" == "$expected" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "pass" "none" "mode=start run_index=$run_index input_len=$input_len expected_len=$expected_len hex_preview=$preview"
  else
    update_fail_counter "output_mismatch"
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "fail" "output_mismatch" "mode=start run_index=$run_index input_len=$input_len expected_len=$expected_len actual_len=${#out} hex_preview=$preview expected_preview=$(preview_hex "$expected") actual_preview=$(preview_hex "$out")"
    FAIL=1
  fi
}

run_invoke_case () {
  local name="$1"
  local case_id="$2"
  local run_index="$3"

  local test_name="$name"
  if [[ "$WASI_REPEAT_RUNS" != "1" ]]; then
    test_name="${name}#run${run_index}"
  fi

  local out err rc
  local errfile
  errfile="$(mktemp -t wasi_invoke_err.XXXXXX)"

  set +e
  out="$("$WASMTIME_BIN" run --invoke codec_wasi_invoke_case "$WASM" "$case_id" 2> "$errfile" | tr -d '\r\n[:space:]')"
  rc=$?
  set -e

  err="$(cat "$errfile")"
  rm -f "$errfile"

  if [[ $rc -ne 0 ]]; then
    local kind
    kind="$(classify_runtime_failure_kind "$(echo "$err" | tr '[:upper:]' '[:lower:]')")"
    update_fail_counter "$kind"
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "fail" "$kind" "mode=invoke run_index=$run_index invoke_case_id=$case_id rc=$rc err=$err"
    FAIL=1
    return
  fi

  if [[ "$out" == "0" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "pass" "none" "mode=invoke run_index=$run_index invoke_case_id=$case_id"
  else
    update_fail_counter "output_mismatch"
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$test_name" "fail" "output_mismatch" "mode=invoke run_index=$run_index invoke_case_id=$case_id returned=$out"
    FAIL=1
  fi
}

run_start_mode_cases () {
  local run_index="$1"

  while IFS=$'\t' read -r case_name case_hex || [[ -n "$case_name" ]]; do
    run_case_hex "$case_name" "$case_hex" "$run_index"
  done < <("$CASE_BIN" \
    --mode "$WASI_MODE" \
    --random-cases "$WASI_RANDOM_CASES" \
    --max-random-len "$WASI_MAX_RANDOM_LEN" \
    --seed "$WASI_RANDOM_SEED")
}

run_invoke_mode_cases () {
  local run_index="$1"

  for ((i=0; i<${#INVOKE_CASE_NAMES[@]}; i++)); do
    run_invoke_case "${INVOKE_CASE_NAMES[$i]}" "$i" "$run_index"
  done
}

for ((run_index=1; run_index<=WASI_REPEAT_RUNS; run_index++)); do
  if [[ "$WASI_EXECUTION_MODE" == "start" || "$WASI_EXECUTION_MODE" == "both" ]]; then
    run_start_mode_cases "$run_index"
  fi

  if [[ "$WASI_EXECUTION_MODE" == "invoke" || "$WASI_EXECUTION_MODE" == "both" ]]; then
    run_invoke_mode_cases "$run_index"
  fi
done

TOTAL_FAIL=$((FAIL_OUTPUT_MISMATCH + FAIL_TRAP + FAIL_EXIT_CODE + FAIL_EXCEPTION))
TOTAL_CASES=$((PASS_COUNT + TOTAL_FAIL))

echo "[Layer2 Summary] mode=$WASI_MODE exec_mode=$WASI_EXECUTION_MODE repeats=$WASI_REPEAT_RUNS total=$TOTAL_CASES pass=$PASS_COUNT fail=$TOTAL_FAIL mismatch=$FAIL_OUTPUT_MISMATCH trap=$FAIL_TRAP exit_code=$FAIL_EXIT_CODE exception=$FAIL_EXCEPTION seed=$WASI_RANDOM_SEED random_cases=$WASI_RANDOM_CASES"

exit $FAIL