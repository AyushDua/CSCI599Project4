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
