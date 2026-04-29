#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
MODULE="${MODULE:-codec}"   # codec | parser | stats
CSV="results/run_results.csv"
JSON="results/gtest_layer1.json"

# Optional knobs:
GTEST_FILTER="${GTEST_FILTER:-*}"
RUN_DISABLED="${RUN_DISABLED:-0}"

case "$MODULE" in
  parser) BINARY="./build/native/test_parser" ;;
  stats)  BINARY="./build/native/test_stats"  ;;
  *)      BINARY="./build/native/test_codec"  ;;
esac

ARGS=( "--gtest_output=json:${JSON}" "--gtest_filter=${GTEST_FILTER}" )
if [[ "$RUN_DISABLED" == "1" ]]; then
  ARGS+=( "--gtest_also_run_disabled_tests" )
fi

set +e
"$BINARY" "${ARGS[@]}"
EXIT_CODE=$?
set -e

python3 scripts/gtest_json_to_csv.py "$JSON" "$CSV" "$BUG_ID"
exit $EXIT_CODE
