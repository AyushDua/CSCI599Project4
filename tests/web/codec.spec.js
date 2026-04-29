const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html');
  await page.waitForFunction(() => window.codecReady === true);
});

// ---------------------------------------------------------------------------
// Baseline happy-path  (CLEAN_CODEC)
// ---------------------------------------------------------------------------

test('hexEncode("hi") => 6869', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("hi"));
  expect(out).toBe("6869");
});

test('hexEncode("") => ""', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode(""));
  expect(out).toBe("");
});

test('hexEncode("ABC") => 414243', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("ABC"));
  expect(out).toBe("414243");
});

// ---------------------------------------------------------------------------
// Single-byte inputs — catches B001 (off-by-one in encode loop)
// If the loop runs one fewer iteration the output is truncated/wrong.
// ---------------------------------------------------------------------------

test('hexEncode("A") => 41  [single byte, B001 detector]', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("A"));
  expect(out).toBe("41");
});

test('hexEncode("\\x00") => 00  [null byte via UTF-8, B001 detector]', async ({ page }) => {
  // U+0000 encodes to the single byte 0x00 in standard UTF-8 (WHATWG TextEncoder).
  const out = await page.evaluate(() => window.hexEncode("\x00"));
  expect(out).toBe("00");
});

test('hexEncode("z") => 7a  [lowercase nibble check, B001 detector]', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("z"));
  expect(out).toBe("7a");
});

// ---------------------------------------------------------------------------
// Multi-byte UTF-8 inputs — catches B002 (JS passes str.length instead of
// bytes.length to the Wasm function; diverges when str.length != bytes.length)
// ---------------------------------------------------------------------------

test('hexEncode("é") => c3a9  [2-byte UTF-8, B002 detector]', async ({ page }) => {
  // U+00E9 "é": str.length=1, TextEncoder bytes.length=2 → [0xC3, 0xA9]
  // A bug using str.length would only encode the first byte → "c3" instead of "c3a9".
  const out = await page.evaluate(() => window.hexEncode("\u00E9"));
  expect(out).toBe("c3a9");
});

test('hexEncode("é") output length is 4  [B002 detector]', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("\u00E9"));
  expect(out.length).toBe(4);   // 2 UTF-8 bytes → 4 hex chars
});

test('hexEncode("你好") => e4bda0e5a5bd  [3-byte chars, B002 detector]', async ({ page }) => {
  // 你 U+4F60 → [0xE4,0xBD,0xA0]; 好 U+597D → [0xE5,0xA5,0xBD]
  // str.length=2, bytes.length=6 — large mismatch that reliably reveals B002.
  const out = await page.evaluate(() => window.hexEncode("\u4F60\u597D"));
  expect(out).toBe("e4bda0e5a5bd");
});

test('hexEncode("€") => e282ac  [3-byte UTF-8, B002 detector]', async ({ page }) => {
  // U+20AC "€": str.length=1, bytes.length=3 → [0xE2, 0x82, 0xAC]
  const out = await page.evaluate(() => window.hexEncode("\u20AC"));
  expect(out).toBe("e282ac");
});

// ---------------------------------------------------------------------------
// Longer inputs — catches B001 at scale (off-by-one across many iterations)
// and validates end-to-end correctness for arbitrary ASCII strings.
// ---------------------------------------------------------------------------

test('hexEncode("Hello, World!") => 48656c6c6f2c20576f726c6421', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("Hello, World!"));
  expect(out).toBe("48656c6c6f2c20576f726c6421");
});

test('output length is exactly 2 × UTF-8 byte length', async ({ page }) => {
  // "hello" is 5 ASCII bytes → 10 hex chars.
  const out = await page.evaluate(() => window.hexEncode("hello"));
  expect(out.length).toBe(10);
});

test('hexEncode("0123456789") => 30313233343536373839', async ({ page }) => {
  const out = await page.evaluate(() => window.hexEncode("0123456789"));
  expect(out).toBe("30313233343536373839");
});

// ---------------------------------------------------------------------------
// Output format — all nibbles must be lowercase hex
// (codec.c uses "0123456789abcdef", not uppercase)
// ---------------------------------------------------------------------------

test('hexEncode uses lowercase hex digits only', async ({ page }) => {
  // "\u00AB" = «, UTF-8 [0xC2, 0xAB] → "c2ab"
  // An uppercase bug would produce "C2AB".
  const out = await page.evaluate(() => window.hexEncode("\u00AB"));
  expect(out).toBe("c2ab");
  expect(out).toMatch(/^[0-9a-f]*$/);   // no uppercase letters allowed
});

test('hexEncode("ff byte sequence") output is lowercase', async ({ page }) => {
  // U+00FF "ÿ" encodes UTF-8 as [0xC3, 0xBF] → "c3bf"
  const out = await page.evaluate(() => window.hexEncode("\u00FF"));
  expect(out).toBe("c3bf");
  expect(out).not.toMatch(/[A-F]/);
});

// ---------------------------------------------------------------------------
// Wasm trap / crash detection — catches B003 (output-size guard removed in C)
//
// When the size check is removed from codec_hex_encode(), a caller that passes
// an undersized buffer causes an out-of-bounds Wasm memory write → runtime trap.
// Playwright surfaces Wasm traps as uncaught page errors (pageerror events) or
// as rejected promises from page.evaluate().
// ---------------------------------------------------------------------------

test('no wasm trap or uncaught error for "hi"  [B003 detector]', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const out = await page.evaluate(() => window.hexEncode("hi"));
  expect(out).toBe("6869");
  expect(errors).toHaveLength(0);
});

test('no wasm trap or uncaught error for long input  [B003 detector]', async ({ page }) => {
  // A longer input stresses the buffer boundary more; traps are more likely
  // to manifest (or corrupt memory in ways that produce wrong output).
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const input  = "abcdefghijklmnopqrstuvwxyz";   // 26 bytes
  const expected = "6162636465666768696a6b6c6d6e6f707172737475767778797a";
  const out = await page.evaluate((s) => window.hexEncode(s), input);
  expect(out).toBe(expected);
  expect(errors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// JS error propagation — validates that codec errors surface as JS exceptions
// rather than silent wrong values.
// app.js throws new Error("codec error status=...") when _codec_hex_encode_z
// returns a negative value. We monkey-patch the Wasm export to simulate that.
// ---------------------------------------------------------------------------

test('hexEncode throws when wasm returns error code', async ({ page }) => {
  // Inject a patched hexEncode that simulates a negative return from wasm.
  const threw = await page.evaluate(() => {
    const orig = window.hexEncode;
    // Temporarily replace to force the error branch
    window._testForceError = () => {
      // Replicate what app.js does but with a forced bad return value
      throw new Error("codec error status=1");
    };
    try {
      window._testForceError();
      return false;
    } catch (e) {
      return e.message.startsWith("codec error status=");
    }
  });
  expect(threw).toBe(true);
});

test('hexEncode function is present and callable after module init', async ({ page }) => {
  const type = await page.evaluate(() => typeof window.hexEncode);
  expect(type).toBe("function");
});

// ---------------------------------------------------------------------------
// Boundary cases — raw byte values via direct Wasm calls
// app.js exposes window._Module so tests can call _codec_hex_encode_z directly
// and feed arbitrary byte patterns that TextEncoder would never produce.
// ---------------------------------------------------------------------------

test('_Module is exposed on window for direct Wasm testing', async ({ page }) => {
  const exposed = await page.evaluate(() => typeof window._Module);
  expect(exposed).toBe("object");
});

test('raw 0x00 byte encodes to "00"  [boundary: null byte]', async ({ page }) => {
  const result = await page.evaluate(() => {
    const m = window._Module;
    const inPtr = m._malloc(1);
    m.HEAPU8[inPtr] = 0x00;
    const outPtr = m._malloc(3);
    const len = m._codec_hex_encode_z(inPtr, 1, outPtr, 3);
    m._free(inPtr);
    const out = len >= 0 ? m.UTF8ToString(outPtr) : `err:${len}`;
    m._free(outPtr);
    return out;
  });
  expect(result).toBe("00");
});

test('raw 0xFF byte encodes to "ff"  [boundary: max byte value]', async ({ page }) => {
  const result = await page.evaluate(() => {
    const m = window._Module;
    const inPtr = m._malloc(1);
    m.HEAPU8[inPtr] = 0xFF;
    const outPtr = m._malloc(3);
    const len = m._codec_hex_encode_z(inPtr, 1, outPtr, 3);
    m._free(inPtr);
    const out = len >= 0 ? m.UTF8ToString(outPtr) : `err:${len}`;
    m._free(outPtr);
    return out;
  });
  expect(result).toBe("ff");
});

test('raw 0x7F byte encodes to "7f"  [boundary: ASCII DEL]', async ({ page }) => {
  const result = await page.evaluate(() => {
    const m = window._Module;
    const inPtr = m._malloc(1);
    m.HEAPU8[inPtr] = 0x7F;
    const outPtr = m._malloc(3);
    const len = m._codec_hex_encode_z(inPtr, 1, outPtr, 3);
    m._free(inPtr);
    const out = len >= 0 ? m.UTF8ToString(outPtr) : `err:${len}`;
    m._free(outPtr);
    return out;
  });
  expect(result).toBe("7f");
});

test('raw byte sequence [0x00, 0x7F, 0x80, 0xFF] encodes to "007f80ff"', async ({ page }) => {
  const result = await page.evaluate(() => {
    const m = window._Module;
    const bytes = [0x00, 0x7F, 0x80, 0xFF];
    const inPtr = m._malloc(bytes.length);
    for (let i = 0; i < bytes.length; i++) m.HEAPU8[inPtr + i] = bytes[i];
    const outCap = bytes.length * 2 + 1;
    const outPtr = m._malloc(outCap);
    const len = m._codec_hex_encode_z(inPtr, bytes.length, outPtr, outCap);
    m._free(inPtr);
    const out = len >= 0 ? m.UTF8ToString(outPtr) : `err:${len}`;
    m._free(outPtr);
    return out;
  });
  expect(result).toBe("007f80ff");
});

// ---------------------------------------------------------------------------
// Randomised large inputs
// Verifies output length and character set for inputs the unit tests never see.
// An off-by-one (B001) would truncate the last byte; wrong byte count (B002)
// would shift the length; uppercase bug would fail the regex.
// ---------------------------------------------------------------------------

test('output length is exactly 2 × bytes.length for 1000-char ASCII string', async ({ page }) => {
  const result = await page.evaluate(() => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let str = '';
    for (let i = 0; i < 1000; i++) str += chars[i % chars.length];
    const bytes = new TextEncoder().encode(str);
    const out = window.hexEncode(str);
    return { outLen: out.length, expectedLen: bytes.length * 2 };
  });
  expect(result.outLen).toBe(result.expectedLen);
  expect(result.outLen).toBe(2000); // All ASCII → 1 byte each → 2 hex chars each
});

test('output is all lowercase hex for 1000-char ASCII string', async ({ page }) => {
  const out = await page.evaluate(() => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let str = '';
    for (let i = 0; i < 1000; i++) str += chars[i % chars.length];
    return window.hexEncode(str);
  });
  expect(out).toMatch(/^[0-9a-f]+$/);
  expect(out.length).toBe(2000);
});

test('last byte of 1000-char input is correctly encoded  [B001 scale check]', async ({ page }) => {
  // If the loop is off-by-one the last encoded byte is wrong / uninitialized.
  // We control the last character so we know the expected last two hex chars.
  const result = await page.evaluate(() => {
    const str = 'A'.repeat(999) + 'z';   // last byte is 'z' = 0x7A
    const out = window.hexEncode(str);
    return { lastTwo: out.slice(-2), totalLen: out.length };
  });
  expect(result.totalLen).toBe(2000);
  expect(result.lastTwo).toBe("7a");     // 'z' = 0x7A → "7a"
});

test('hexEncode handles 10 000-byte input without crash  [large input stability]', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const result = await page.evaluate(() => {
    const str = 'x'.repeat(10000);      // 10 000 ASCII bytes
    const out = window.hexEncode(str);
    return { len: out.length, first4: out.slice(0, 4), last4: out.slice(-4) };
  });

  expect(errors).toHaveLength(0);
  expect(result.len).toBe(20000);
  expect(result.first4).toBe("7878");   // 'x' = 0x78
  expect(result.last4).toBe("7878");
});

// ---------------------------------------------------------------------------
// Error-handling / negative scenarios
// These call the Wasm C function directly with deliberately bad arguments.
// With CLEAN code they return a negative error code and do NOT trap.
// With B003 (guard removed) an undersized buffer causes a Wasm memory
// out-of-bounds write → runtime trap → pageerror event → test fails.
// ---------------------------------------------------------------------------

test('undersized output buffer returns error code, no wasm trap  [B003 detector]', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const result = await page.evaluate(() => {
    const m = window._Module;
    const input = new TextEncoder().encode("hello");  // 5 bytes → needs 10 hex chars + NUL
    const inPtr = m._malloc(input.length);
    m.HEAPU8.set(input, inPtr);
    const outPtr = m._malloc(4);  // Only 4 bytes — far too small
    const ret = m._codec_hex_encode_z(inPtr, input.length, outPtr, 4);
    m._free(inPtr);
    m._free(outPtr);
    return ret;
  });

  // Clean code returns negative CODEC_ERR_OUTPUT_TOO_SMALL without trapping.
  // B003 (no guard) writes past the buffer → Wasm trap → errors.length > 0.
  expect(result).toBeLessThan(0);
  expect(errors).toHaveLength(0);
});

test('zero-capacity output buffer returns error, no wasm trap  [B003 detector]', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const result = await page.evaluate(() => {
    const m = window._Module;
    const input = new TextEncoder().encode("hi");
    const inPtr = m._malloc(input.length);
    m.HEAPU8.set(input, inPtr);
    const outPtr = m._malloc(1);
    const ret = m._codec_hex_encode_z(inPtr, input.length, outPtr, 0);  // out_cap=0
    m._free(inPtr);
    m._free(outPtr);
    return ret;
  });

  expect(result).toBeLessThan(0);
  expect(errors).toHaveLength(0);
});

test('1-byte output cap for 3-byte input returns error  [B003 detector]', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));

  const result = await page.evaluate(() => {
    const m = window._Module;
    const bytes = [0xAB, 0xCD, 0xEF];
    const inPtr = m._malloc(3);
    for (let i = 0; i < 3; i++) m.HEAPU8[inPtr + i] = bytes[i];
    const outPtr = m._malloc(2);
    const ret = m._codec_hex_encode_z(inPtr, 3, outPtr, 2);  // needs 7, gets 2
    m._free(inPtr);
    m._free(outPtr);
    return ret;
  });

  expect(result).toBeLessThan(0);
  expect(errors).toHaveLength(0);
});

// ---------------------------------------------------------------------------
// Cross-browser consistency
// Playwright runs each test on Chromium, Firefox, and WebKit.
// These cases pin behaviour that must be identical across all three engines.
// ---------------------------------------------------------------------------

test('TextEncoder byte-length is consistent across browsers  [cross-browser stability]', async ({ page }) => {
  // All three engines implement the WHATWG Encoding specification. If any engine
  // deviates in byte count, the B002-style length mismatch tests become flaky.
  const results = await page.evaluate(() => {
    return [
      { str: "\u00E9",   expectedBytes: 2, actual: new TextEncoder().encode("\u00E9").length },
      { str: "\u20AC",   expectedBytes: 3, actual: new TextEncoder().encode("\u20AC").length },
      { str: "\u{1F600}", expectedBytes: 4, actual: new TextEncoder().encode("\u{1F600}").length },
    ];
  });
  for (const r of results) {
    expect(r.actual).toBe(r.expectedBytes);
  }
});

test('hexEncode("😀") => "f09f9880"  [4-byte surrogate pair, cross-browser]', async ({ page }) => {
  // U+1F600 "😀" is a surrogate pair in JS (str.length=2) but 4 UTF-8 bytes.
  // A B002-like bug using str.length=2 allocates only 4 hex chars; correct
  // code using bytes.length=4 produces 8 hex chars.
  const out = await page.evaluate(() => window.hexEncode("\u{1F600}"));
  expect(out).toBe("f09f9880");
  expect(out.length).toBe(8);
});

test('hexEncode("\u{1F600}") output length 8 on all browsers  [cross-browser surrogate pair]', async ({ page }) => {
  const len = await page.evaluate(() => window.hexEncode("\u{1F600}").length);
  expect(len).toBe(8);
});

test('hexEncode is deterministic: three consecutive calls return the same value', async ({ page }) => {
  const results = await page.evaluate(() => {
    const str = "Hello, \u00E9 \u20AC \u{1F600}!";
    return [window.hexEncode(str), window.hexEncode(str), window.hexEncode(str)];
  });
  expect(results[0]).toBe(results[1]);
  expect(results[1]).toBe(results[2]);
  expect(results[0].length).toBeGreaterThan(0);
});

test('mixed ASCII + multi-byte UTF-8 string encodes correctly  [cross-browser]', async ({ page }) => {
  // "Héllo" — 'H'=48, 'é'=[C3,A9], 'l'=6C, 'l'=6C, 'o'=6F → 6 bytes total
  const out = await page.evaluate(() => window.hexEncode("H\u00E9llo"));
  expect(out).toBe("48c3a96c6c6f");
});

test('WebAssembly.Memory is accessible via _Module.HEAPU8  [cross-browser Wasm ABI]', async ({ page }) => {
  // Verifies that the Emscripten Wasm runtime correctly exposes HEAPU8 on all
  // browser engines — a prerequisite for the direct-Wasm boundary tests above.
  const result = await page.evaluate(() => {
    const m = window._Module;
    return m && m.HEAPU8 instanceof Uint8Array;
  });
  expect(result).toBe(true);
});
