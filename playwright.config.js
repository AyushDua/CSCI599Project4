// playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/web',
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:5173', headless: true },
  webServer: {
    command: 'python -m http.server 5173 --directory web',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
  },
  reporter: [
    ['list'],
    ['json', { outputFile: 'results/playwright_layer3.json' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }]
  ],
  projects: [
    { name: 'Chromium', use: { browserName: 'chromium' } },
    { name: 'Firefox',  use: { browserName: 'firefox' } },
    { name: 'WebKit',   use: { browserName: 'webkit' } }
  ],
});
