#!/usr/bin/env bash
set -euo pipefail

# Detect python — try python first, verify it actually runs (Windows Store
# stub reports as found but exits 49 without executing anything).
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

./scripts/build_native.sh

# Layer 1 — all three modules (clean build)
./scripts/test_native.sh
MODULE=parser ./scripts/test_native.sh
MODULE=stats  ./scripts/test_native.sh

./scripts/build_wasi.sh
./scripts/test_wasi.sh

# Layer 3 — full matrix: codec, parser, and stats variants
./scripts/run_layer3_matrix.sh \
  CLEAN_CODEC:. B001_CODEC:. B002_CODEC:. B003_CODEC:. \
  CLEAN_PARSER:. Q001_PARSER:. Q002_PARSER:. Q003_PARSER:. Q004_PARSER:. \
  CLEAN_STATS:. S001_STATS:. S002_STATS:. S003_STATS:. S004_STATS:.

# Layer 1 charts
"$PYTHON" scripts/render_layer1_chart.py

# Cross-layer analysis and ML classification
"$PYTHON" scripts/analyze_cross_layer.py
"$PYTHON" scripts/ml_bug_classifier.py

echo "ALL SMOKE TESTS PASSED"
