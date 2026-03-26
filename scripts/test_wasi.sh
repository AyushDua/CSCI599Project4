#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="results/run_results.csv"
WASM="build/wasi/codec_wasi.wasm"
WASI_MODE="${WASI_MODE:-fast}"   # fast or full

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
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "fail" "$kind" "input_len=$input_len expected_len=$expected_len hex_preview=$preview rc=$rc err=$err"
    FAIL=1
    return
  fi

  if [[ "$out" == "$expected" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "pass" "none" "input_len=$input_len expected_len=$expected_len hex_preview=$preview"
  else
    update_fail_counter "output_mismatch"
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "fail" "output_mismatch" "input_len=$input_len expected_len=$expected_len actual_len=${#out} hex_preview=$preview expected_preview=$(preview_hex "$expected") actual_preview=$(preview_hex "$out")"
    FAIL=1
  fi
}

declare -a CASE_NAMES=()
declare -a CASE_HEX=()

add_case () {
  CASE_NAMES+=("$1")
  CASE_HEX+=("$2")
}

# Canonical smoke + boundary cases.
add_case "stdin_empty" ""
add_case "stdin_hi" "6869"
add_case "stdin_ABC" "414243"
add_case "stdin_bytes_000102" "000102"
add_case "single_00" "00"
add_case "single_ff" "ff"
add_case "mixed_0001027f80ff" "0001027f80ff"
add_case "ascii_sentence" "5761736d206c617965722032"
add_case "repeating_ab_16" "$(python3 - <<'PY'
print('ab' * 16)
PY
)"

# Length boundary cases near powers of two and stdin buffer limit.
add_case "boundary_len_1" "$(python3 - <<'PY'
print('42' * 1)
PY
)"
add_case "boundary_len_2" "$(python3 - <<'PY'
print('42' * 2)
PY
)"
add_case "boundary_len_3" "$(python3 - <<'PY'
print('42' * 3)
PY
)"
add_case "boundary_len_255" "$(python3 - <<'PY'
print('42' * 255)
PY
)"
add_case "boundary_len_256" "$(python3 - <<'PY'
print('42' * 256)
PY
)"
add_case "boundary_len_1023" "$(python3 - <<'PY'
print('42' * 1023)
PY
)"
add_case "boundary_len_4096" "$(python3 - <<'PY'
print('42' * 4096)
PY
)"

if [[ "$WASI_MODE" == "full" ]]; then
  add_case "boundary_len_4095" "$(python3 - <<'PY'
print('37' * 4095)
PY
)"
fi

for ((i=0; i<${#CASE_NAMES[@]}; i++)); do
  run_case_hex "${CASE_NAMES[$i]}" "${CASE_HEX[$i]}"
done

# Deterministic pseudo-random vectors for broader behavior coverage.
RAND_INDEX=0
while IFS= read -r hex_line; do
  run_case_hex "random_seed_${WASI_RANDOM_SEED}_${RAND_INDEX}" "$hex_line"
  RAND_INDEX=$((RAND_INDEX + 1))
done < <(python3 - "$WASI_RANDOM_CASES" "$WASI_MAX_RANDOM_LEN" "$WASI_RANDOM_SEED" <<'PY'
import random
import sys

case_count = int(sys.argv[1])
max_len = int(sys.argv[2])
seed = int(sys.argv[3])
rng = random.Random(seed)

for _ in range(case_count):
    n = rng.randint(0, max_len)
    b = bytes(rng.getrandbits(8) for _ in range(n))
    print(b.hex())
PY
)

TOTAL_FAIL=$((FAIL_OUTPUT_MISMATCH + FAIL_TRAP + FAIL_EXIT_CODE + FAIL_EXCEPTION))
TOTAL_CASES=$((PASS_COUNT + TOTAL_FAIL))

echo "[Layer2 Summary] mode=$WASI_MODE total=$TOTAL_CASES pass=$PASS_COUNT fail=$TOTAL_FAIL mismatch=$FAIL_OUTPUT_MISMATCH trap=$FAIL_TRAP exit_code=$FAIL_EXIT_CODE exception=$FAIL_EXCEPTION seed=$WASI_RANDOM_SEED random_cases=$WASI_RANDOM_CASES"

exit $FAIL