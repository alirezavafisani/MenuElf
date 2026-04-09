import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,
  },
  webServer: {
    command: 'python3 tests/test-server.py',
    port: 8000,
    timeout: 15000,
    reuseExistingServer: true,
  },
});
