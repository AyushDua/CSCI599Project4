#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/env.sh"

OUT_DIR="$ROOT_DIR/build/wasi"
mkdir -p "$OUT_DIR"

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
EXTRA_CFLAGS=()

case "$BUG_ID" in
  CLEAN_CODEC|CLEAN_PARSER|CLEAN_STATS|"") ;;
  # Codec bugs
  B001_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B001=1") ;;
  B003_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B003=1") ;;
  B004_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B004=1") ;;
  B005_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B005=1") ;;
  B006_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B006=1") ;;
  B007_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B007=1") ;;
  B008_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B008=1") ;;
  # Parser bugs
  Q001_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q001=1") ;;
  Q002_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q002=1") ;;
  Q003_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q003=1") ;;
  Q004_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q004=1") ;;
  # Stats bugs
  S001_STATS) EXTRA_CFLAGS+=("-DSTATS_BUG_S001=1") ;;
  S002_STATS) EXTRA_CFLAGS+=("-DSTATS_BUG_S002=1") ;;
  S003_STATS) EXTRA_CFLAGS+=("-DSTATS_BUG_S003=1") ;;
  S004_STATS) EXTRA_CFLAGS+=("-DSTATS_BUG_S004=1") ;;
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