#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/emsdk_env.sh"

mkdir -p "$ROOT_DIR/web"

emcc "$ROOT_DIR/src/codec.c" "$ROOT_DIR/src/web_api.c" \
  -I"$ROOT_DIR/src" -O0 -g \
  -s MODULARIZE=1 \
  -s EXPORT_ES6=1 \
  -s EXPORTED_FUNCTIONS="['_codec_hex_encode_z','_malloc','_free']" \
  -s 'EXPORTED_RUNTIME_METHODS=["UTF8ToString","HEAPU8"]' \
  -o "$ROOT_DIR/web/codec_web.js"