#!/usr/bin/env bash
set -euo pipefail

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
CSV="results/run_results.csv"
PW_JSON="results/playwright_layer3.json"

./scripts/build_web.sh

# Remove stale report so we don't parse an old file if Playwright crashes early
rm -f "$PW_JSON"

set +e
npx playwright test
EXIT_CODE=$?
set -e

# Always parse (even if tests failed)
python3 scripts/playwright_json_to_csv.py "$PW_JSON" "$CSV" "$BUG_ID"

exit $EXIT_CODE