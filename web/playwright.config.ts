import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.CALIPER_E2E_BASE_URL ?? 'https://127.0.0.1:18443',
    ignoreHTTPSErrors: true,
    browserName: 'chromium',
    trace: 'retain-on-failure',
  },
})
