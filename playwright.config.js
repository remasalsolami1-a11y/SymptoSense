const { defineConfig, devices } = require('@playwright/test');
module.exports = defineConfig({
  testDir: '.', timeout: 30000, retries: 1,
  use: { baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5000', trace: 'retain-on-failure' },
  projects: [
    { name: 'mobile-390', use: { viewport: { width: 390, height: 844 } } },
    { name: 'mobile-430', use: { viewport: { width: 430, height: 932 } } },
    { name: 'ipad', use: { ...devices['iPad (gen 7)'] } },
    { name: 'desktop', use: { viewport: { width: 1366, height: 768 } } }
  ]
});
