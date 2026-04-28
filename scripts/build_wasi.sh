#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/env.sh"

OUT_DIR="$ROOT_DIR/build/wasi"
mkdir -p "$OUT_DIR"

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
EXTRA_CFLAGS=()

case "$BUG_ID" in
  CLEAN_CODEC|"") ;;
  B001_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B001=1") ;;
  B003_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B003=1") ;;
  *)
    echo "Unknown or unsupported WASI bug variant: $BUG_ID"
    exit 2
    ;;
esac

CLANG_ARGS=(
  --target=wasm32-wasip1
  --sysroot="$WASI_SDK_PATH/share/wasi-sysroot"
  -O0
  -g
  -Wl,--export=codec_wasi_invoke_case
  -Wl,--export=codec_wasi_case_count
  "$ROOT_DIR/src/codec.c"
  "$ROOT_DIR/src/wasi_main.c"
  -I"$ROOT_DIR/src"
  -o "$OUT_DIR/codec_wasi.wasm"
)

if [[ ${#EXTRA_CFLAGS[@]} -gt 0 ]]; then
  CLANG_ARGS=("${EXTRA_CFLAGS[@]}" "${CLANG_ARGS[@]}")
fi

"$WASI_SDK_PATH/bin/clang" "${CLANG_ARGS[@]}"