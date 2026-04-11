import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  retries: 0,
  // Run serially because several tests compare /stats before/after and would
  // contaminate each other's event counts under parallel execution.
  workers: 1,
  fullyParallel: false,
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
