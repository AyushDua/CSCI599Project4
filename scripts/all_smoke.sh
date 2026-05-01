#!/usr/bin/env bash
set -euo pipefail

./scripts/build_native.sh

# Layer 1 — all three modules (clean build)
./scripts/test_native.sh
MODULE=parser ./scripts/test_native.sh
MODULE=stats  ./scripts/test_native.sh

./scripts/build_wasi.sh
./scripts/test_wasi.sh
python3 scripts/analyze_layer2_results.py --no-render-chart --no-open-chart

./scripts/test_web.sh
python3 scripts/analyze_layer3_results.py --csv results/run_results.csv --no-render-chart --no-open-chart

# Layer 1 charts
python3 scripts/render_layer1_chart.py

# Layer 2 / Layer 3 charts
python3 scripts/render_layer2_chart.py
python3 scripts/render_layer3_chart.py

# Cross-layer analysis and ML classification
python3 scripts/analyze_cross_layer.py
python3 scripts/ml_bug_classifier.py

# Aggregate cross-layer PNG charts (requires pandas + matplotlib; skip if absent)
if python3 -c "import pandas, matplotlib" 2>/dev/null; then
  python3 scripts/make_charts.py
else
  echo "[charts] skipping make_charts.py (pandas/matplotlib not installed)"
fi

# Collect all chart files into results/charts/
mkdir -p results/charts
cp -f results/layer1_chart.svg        results/charts/ 2>/dev/null || true
cp -f results/layer1_chart.html       results/charts/ 2>/dev/null || true
cp -f results/layer1_visual_matrix.svg results/charts/ 2>/dev/null || true
cp -f results/layer2_chart.svg        results/charts/ 2>/dev/null || true
cp -f results/layer2_chart.html       results/charts/ 2>/dev/null || true
cp -f results/layer2_visual_matrix.svg results/charts/ 2>/dev/null || true
cp -f results/layer3_chart.svg        results/charts/ 2>/dev/null || true
cp -f results/layer3_chart.html       results/charts/ 2>/dev/null || true
cp -f results/layer3_visual_matrix.svg results/charts/ 2>/dev/null || true
cp -f results/cross_layer_heatmap.svg  results/charts/ 2>/dev/null || true
cp -f results/ml_feature_importance_dt.svg results/charts/ 2>/dev/null || true
cp -f results/ml_feature_importance_rf.svg results/charts/ 2>/dev/null || true
echo "[charts] synced to results/charts/"

echo "ALL SMOKE TESTS PASSED"
