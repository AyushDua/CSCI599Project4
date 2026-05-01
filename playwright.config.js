// playwright.config.js
const { defineConfig } = require('@playwright/test');
const { execSync } = require('child_process');

function detectPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  for (const cmd of ['python', 'python3']) {
    try {
      execSync(`${cmd} -c ""`, { stdio: 'ignore' });
      return cmd;
    } catch (_) {}
  }
  throw new Error('python not found on PATH');
}

const python = detectPython();

module.exports = defineConfig({
  testDir: './tests/web',
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:5173', headless: true },
  webServer: {
    command: `${python} -m http.server 5173 --directory web`,
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
