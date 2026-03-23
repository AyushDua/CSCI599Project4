#!/usr/bin/env bash
set -euo pipefail

echo "==> Checking basics"
command -v brew >/dev/null 2>&1 || { echo "Homebrew not found. Install from https://brew.sh"; exit 1; }
command -v wasmtime >/dev/null 2>&1 || { echo "Wasmtime not found. Run: brew install wasmtime"; exit 1; }

echo "==> Installing project tools into .tools/"
./scripts/install_wasi_sdk.sh
./scripts/install_emsdk.sh

echo "==> Node deps"
npm install
npx playwright install

echo "==> Done."