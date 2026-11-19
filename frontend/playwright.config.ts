import { defineConfig, devices } from "@playwright/test";

import { AUTH_STATE } from "./e2e/auth";

import { BASE_URL, VIEWPORT } from "./e2e/simulation";

const desktop = { ...devices["Desktop Chrome"], viewport: VIEWPORT };

/** Runs against the demo stack (`make test-e2e`), never against mocks (architecture §08). */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/auth-setup.ts",
  timeout: 120_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    storageState: AUTH_STATE,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testMatch: "**/*.e2e.ts",
      use: desktop,
    },
    {
      // Not a test: README screenshots.
      name: "screenshots",
      testMatch: "**/*.capture.ts",
      use: desktop,
    },
  ],
});
