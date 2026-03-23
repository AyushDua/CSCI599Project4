#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="results/run_results.csv"
JSON="results/gtest_layer1.json"

# Optional knobs:
GTEST_FILTER="${GTEST_FILTER:-*}"
RUN_DISABLED="${RUN_DISABLED:-0}"

ARGS=( "--gtest_output=json:${JSON}" "--gtest_filter=${GTEST_FILTER}" )
if [[ "$RUN_DISABLED" == "1" ]]; then
  ARGS+=( "--gtest_also_run_disabled_tests" )
fi

set +e
./build/native/test_codec "${ARGS[@]}"
EXIT_CODE=$?
set -e

python3 scripts/gtest_json_to_csv.py "$JSON" "$CSV" "$BUG_ID"
exit $EXIT_CODE