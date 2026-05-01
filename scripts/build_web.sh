#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/emsdk_env.sh"

mkdir -p "$ROOT_DIR/web"

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
EXTRA_CFLAGS=()

case "$BUG_ID" in
  CLEAN_CODEC|CLEAN_PARSER|CLEAN_STATS|"") ;;
  B001_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B001=1") ;;
  B002_CODEC) ;;  # JS-side bug: no C flag needed
  B003_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B003=1") ;;
  Q001_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q001=1") ;;
  Q002_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q002=1") ;;
  Q003_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q003=1") ;;
  Q004_PARSER) EXTRA_CFLAGS+=("-DPARSER_BUG_Q004=1") ;;
  S001_STATS)  EXTRA_CFLAGS+=("-DSTATS_BUG_S001=1") ;;
  S002_STATS)  EXTRA_CFLAGS+=("-DSTATS_BUG_S002=1") ;;
  S003_STATS)  EXTRA_CFLAGS+=("-DSTATS_BUG_S003=1") ;;
  S004_STATS)  EXTRA_CFLAGS+=("-DSTATS_BUG_S004=1") ;;
  *)
    echo "Unknown or unsupported web bug variant: $BUG_ID"
    exit 2
    ;;
esac

EMCC_ARGS=(
  "$ROOT_DIR/src/codec.c"
  "$ROOT_DIR/src/parser.c"
  "$ROOT_DIR/src/stats.c"
  "$ROOT_DIR/src/web_api.c"
  -I"$ROOT_DIR/src"
  -O0 -g
  -s MODULARIZE=1
  -s EXPORT_ES6=1
  -s EXPORTED_FUNCTIONS="['_codec_hex_encode_z','_parser_get_field_z','_parser_next_field_raw_z','_parser_count_fields_z','_stats_sum_z','_stats_min_z','_stats_max_z','_stats_mean_z','_stats_dot_z','_malloc','_free']"
  -s 'EXPORTED_RUNTIME_METHODS=["UTF8ToString","HEAPU8","HEAP32","HEAPF32","HEAPF64"]'
  -o "$ROOT_DIR/web/codec_web.js"
)

if [[ ${#EXTRA_CFLAGS[@]} -gt 0 ]]; then
  EMCC_ARGS=("${EXTRA_CFLAGS[@]}" "${EMCC_ARGS[@]}")
fi

emcc "${EMCC_ARGS[@]}"

# Write the appropriate app.js for this bug variant.
# B002 is a JS-side bug: str.length is passed instead of bytes.length,
# which diverges for any multi-byte UTF-8 character.
if [[ "$BUG_ID" == "B002_CODEC" ]]; then
  cat > "$ROOT_DIR/web/app.js" << 'APPJS'
import createModule from './codec_web.js';

const statusEl = document.getElementById('status');

(async () => {
  const Module = await createModule();

  window.codecReady = true;
  window._Module = Module;

  window.hexEncode = (str) => {
    const bytes = new TextEncoder().encode(str);

    const inPtr = Module._malloc(bytes.length);
    Module.HEAPU8.set(bytes, inPtr);

    const outCap = bytes.length * 2 + 1;
    const outPtr = Module._malloc(outCap);

    // B002: passes str.length instead of bytes.length
    const len = Module._codec_hex_encode_z(inPtr, str.length, outPtr, outCap);

    Module._free(inPtr);

    if (len < 0) {
      Module._free(outPtr);
      throw new Error("codec error status=" + (-len));
    }

    const outStr = Module.UTF8ToString(outPtr);
    Module._free(outPtr);
    return outStr;
  };

  statusEl.textContent = "ready";
})();
APPJS
else
  cat > "$ROOT_DIR/web/app.js" << 'APPJS'
import createModule from './codec_web.js';

const statusEl = document.getElementById('status');

(async () => {
  const Module = await createModule();

  window.codecReady = true;
  window._Module = Module;

  window.hexEncode = (str) => {
    const bytes = new TextEncoder().encode(str);

    const inPtr = Module._malloc(bytes.length);
    Module.HEAPU8.set(bytes, inPtr);

    const outCap = bytes.length * 2 + 1;
    const outPtr = Module._malloc(outCap);

    const len = Module._codec_hex_encode_z(inPtr, bytes.length, outPtr, outCap);

    Module._free(inPtr);

    if (len < 0) {
      Module._free(outPtr);
      throw new Error("codec error status=" + (-len));
    }

    const outStr = Module.UTF8ToString(outPtr);
    Module._free(outPtr);
    return outStr;
  };

  statusEl.textContent = "ready";
})();
APPJS
fi

# Append parser and stats JS helpers to app.js.
# These live outside the async IIFE and access window._Module at call time,
# which is safe because tests wait for window.codecReady before calling them.
cat >> "$ROOT_DIR/web/app.js" << 'HELPERS'

// --- parser helpers (access window._Module at call time) ---

window.parseCSVField = (csvStr, fieldIndex) => {
  const M = window._Module;
  const bytes = new TextEncoder().encode(csvStr);
  const inPtr = M._malloc(bytes.length || 1);
  M.HEAPU8.set(bytes, inPtr);
  const outCap = bytes.length + 2;
  const outPtr = M._malloc(outCap);
  const len = M._parser_get_field_z(inPtr, bytes.length, fieldIndex, outPtr, outCap);
  M._free(inPtr);
  if (len < 0) { M._free(outPtr); throw new Error("parser error status=" + (-len)); }
  const result = M.UTF8ToString(outPtr);
  M._free(outPtr);
  return result;
};

window.countCSVFields = (csvStr) => {
  const M = window._Module;
  const bytes = new TextEncoder().encode(csvStr);
  const inPtr = M._malloc(bytes.length || 1);
  M.HEAPU8.set(bytes, inPtr);
  const count = M._parser_count_fields_z(inPtr, bytes.length);
  M._free(inPtr);
  return count;
};

// --- stats helpers ---

window.statsSum = (arr) => {
  const M = window._Module;
  const typed = new Int32Array(arr);
  const ptr = M._malloc(typed.byteLength || 4);
  M.HEAPU8.set(new Uint8Array(typed.buffer), ptr);
  const result = M._stats_sum_z(ptr, typed.length);
  M._free(ptr);
  return result;
};

window.statsMin = (arr) => {
  const M = window._Module;
  const typed = new Int32Array(arr);
  const ptr = M._malloc(typed.byteLength || 4);
  M.HEAPU8.set(new Uint8Array(typed.buffer), ptr);
  const result = M._stats_min_z(ptr, typed.length);
  M._free(ptr);
  return result;
};

window.statsMax = (arr) => {
  const M = window._Module;
  const typed = new Int32Array(arr);
  const ptr = M._malloc(typed.byteLength || 4);
  M.HEAPU8.set(new Uint8Array(typed.buffer), ptr);
  const result = M._stats_max_z(ptr, typed.length);
  M._free(ptr);
  return result;
};

window.statsMean = (arr) => {
  const M = window._Module;
  const typed = new Float64Array(arr);
  const ptr = M._malloc(typed.byteLength || 8);
  M.HEAPU8.set(new Uint8Array(typed.buffer), ptr);
  const result = M._stats_mean_z(ptr, typed.length);
  M._free(ptr);
  return result;
};

window.statsDot = (arrA, arrB) => {
  const M = window._Module;
  const typedA = new Float32Array(arrA);
  const typedB = new Float32Array(arrB);
  const ptrA = M._malloc(typedA.byteLength || 4);
  const ptrB = M._malloc(typedB.byteLength || 4);
  M.HEAPU8.set(new Uint8Array(typedA.buffer), ptrA);
  M.HEAPU8.set(new Uint8Array(typedB.buffer), ptrB);
  const result = M._stats_dot_z(ptrA, ptrB, typedA.length);
  M._free(ptrA);
  M._free(ptrB);
  return result;
};
HELPERS

echo "[build_web] bug_id=$BUG_ID done"
