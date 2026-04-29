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

    /* B002: passes str.length instead of bytes.length — diverges for multi-byte UTF-8 */
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
