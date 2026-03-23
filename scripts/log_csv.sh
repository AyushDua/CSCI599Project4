#!/usr/bin/env bash
set -euo pipefail

CSV_FILE="${1:?csv file path}"
shift

# args: bug_id layer runtime test_name outcome details
BUG_ID="${1:?}"; LAYER="${2:?}"; RUNTIME="${3:?}"; TEST_NAME="${4:?}"
OUTCOME="${5:?}"; FAILURE_KIND="${6-}"; DETAILS="${7-}"

mkdir -p "$(dirname "$CSV_FILE")"

if [[ ! -f "$CSV_FILE" ]]; then
  echo "timestamp,bug_id,layer,runtime,test_name,outcome,failure_kind,details" > "$CSV_FILE"
fi

TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
# escape quotes in details
DETAILS_ESCAPED="${DETAILS//\"/\"\"}"

echo "$TS,$BUG_ID,$LAYER,$RUNTIME,$TEST_NAME,$OUTCOME,$FAILURE_KIND,\"$DETAILS_ESCAPED\"" >> "$CSV_FILE"