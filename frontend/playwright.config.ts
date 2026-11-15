import { defineConfig, devices } from "@playwright/test";

/** Runs against the Compose stack (`make up`), never against mocks (architecture §08). */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 120_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.IPHI_E2E_URL ?? "http://127.0.0.1:8080",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
});
