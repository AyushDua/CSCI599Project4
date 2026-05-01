#!/usr/bin/env bash
set -euo pipefail

./scripts/build_native.sh

# Layer 1 — all three modules (clean build)
./scripts/test_native.sh
MODULE=parser ./scripts/test_native.sh
MODULE=stats  ./scripts/test_native.sh

./scripts/build_wasi.sh
./scripts/test_wasi.sh

./scripts/test_web.sh

# Layer 1 charts
python3 scripts/render_layer1_chart.py

# Cross-layer analysis and ML classification
python3 scripts/analyze_cross_layer.py
python3 scripts/ml_bug_classifier.py

echo "ALL SMOKE TESTS PASSED"
