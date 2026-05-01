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
