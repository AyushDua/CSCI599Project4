#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/env.sh"

OUT_DIR="$ROOT_DIR/build/wasi"
mkdir -p "$OUT_DIR"

"$WASI_SDK_PATH/bin/clang" \
  --target=wasm32-wasip1 \
  --sysroot="$WASI_SDK_PATH/share/wasi-sysroot" \
  -O0 -g \
  "$ROOT_DIR/src/codec.c" "$ROOT_DIR/src/wasi_main.c" \
  -I"$ROOT_DIR/src" \
  -o "$OUT_DIR/codec_wasi.wasm"