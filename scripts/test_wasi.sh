#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="results/run_results.csv"
WASM="build/wasi/codec_wasi.wasm"

FAIL=0

run_case () {
  local name="$1"
  local expected="$2"
  local input_cmd="$3"

  local out err rc
  local errfile
  errfile="$(mktemp -t wasi_err.XXXXXX)"

  # Capture output + exit code safely even under set -e
  set +e
  out="$(bash -lc "$input_cmd" | wasmtime run "$WASM" 2> "$errfile" | tr -d '\n')"
  rc=$?
  set -e

  err="$(cat "$errfile")"
  rm -f "$errfile"

  if [[ $rc -ne 0 ]]; then
    # Wasmtime trap messages commonly include "wasm trap:" in stderr. :contentReference[oaicite:1]{index=1}
    if echo "$err" | grep -qi "wasm trap:"; then
      ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "fail" "trap" "$err"
    else
      ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "fail" "exit_code" "rc=$rc err=$err"
    fi
    FAIL=1
    return
  fi

  if [[ "$out" == "$expected" ]]; then
    # IMPORTANT: Don't pass empty failure_kind because log_csv.sh uses ${6:?}
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "pass" "none" ""
  else
    ./scripts/log_csv.sh "$CSV" "$BUG_ID" "layer2_wasmtime" "wasmtime" "$name" "fail" "output_mismatch" "expected=$expected actual=$out"
    FAIL=1
  fi
}

run_case "stdin_empty" "" "printf ''"
run_case "stdin_hi" "6869" "printf 'hi'"
run_case "stdin_ABC" "414243" "printf 'ABC'"
run_case "stdin_bytes_000102" "000102" "printf '\x00\x01\x02'"

exit $FAIL