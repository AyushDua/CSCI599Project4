#!/usr/bin/env bash
set -euo pipefail

./scripts/build_native.sh
./scripts/test_native.sh

./scripts/build_wasi.sh
./scripts/test_wasi.sh

./scripts/test_web.sh

echo "ALL SMOKE TESTS PASSED"