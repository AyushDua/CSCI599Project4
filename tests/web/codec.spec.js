const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html');
  await page.waitForFunction(() => window.codecReady === true);
});

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