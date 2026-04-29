#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/.tools/emsdk_env.sh"

mkdir -p "$ROOT_DIR/web"

BUG_ID="${BUG_ID:-CLEAN_CODEC}"
EXTRA_CFLAGS=()

case "$BUG_ID" in
  CLEAN_CODEC|"") ;;
  B001_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B001=1") ;;
  B002_CODEC) ;;  # JS-side bug: no C flag needed
  B003_CODEC) EXTRA_CFLAGS+=("-DCODEC_BUG_B003=1") ;;
  *)
    echo "Unknown or unsupported web bug variant: $BUG_ID"
    exit 2
    ;;
esac

EMCC_ARGS=(
  "$ROOT_DIR/src/codec.c"
  "$ROOT_DIR/src/web_api.c"
  -I"$ROOT_DIR/src"
  -O0 -g
  -s MODULARIZE=1
  -s EXPORT_ES6=1
  -s EXPORTED_FUNCTIONS="['_codec_hex_encode_z','_malloc','_free']"
  -s 'EXPORTED_RUNTIME_METHODS=["UTF8ToString","HEAPU8"]'
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

echo "[build_web] bug_id=$BUG_ID done"
