import { defineConfig } from "@playwright/test";

/**
 * EdgeErgo Minimal Playwright E2E Configuration
 * Tests responsive layouts at 1280px (desktop), 820px (tablet), and 390px (mobile).
 * Marked as optional in CI if heavy/browser binaries not pre-installed.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:4173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "desktop-1280",
      use: {
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: "tablet-820",
      use: {
        viewport: { width: 820, height: 1180 },
      },
    },
    {
      name: "mobile-390",
      use: {
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: {
    command: "npm run preview -- --port 4173",
    port: 4173,
    reuseExistingServer: !process.env.CI,
  },
});
