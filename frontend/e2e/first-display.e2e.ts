import { expect, test } from "@playwright/test";

import { BASE_URL, componentRow, VIEWPORT } from "./simulation";

/** Architecture §07.2: first display of the dashboard under 2 s on the production build. */
const TARGET_MS = 2_000;
const LOADS = 5;

test("first display of the Overview stays under 2 s", async ({ browser }, testInfo) => {
  const durations: number[] = [];
  for (let load = 0; load < LOADS; load += 1) {
    // Empty cache per load; hand-made contexts do not inherit the configuration's `use`.
    const context = await browser.newContext({ baseURL: BASE_URL, viewport: VIEWPORT });
    const page = await context.newPage();
    const started = performance.now();
    await page.goto("/", { waitUntil: "commit" });
    await expect(componentRow(page, "collector-01")).toBeVisible();
    durations.push(Math.round(performance.now() - started));
    await context.close();
  }
  const report = `first display, navigation to component states visible: ${durations.join(", ")} ms`;
  testInfo.annotations.push({ type: "measure", description: report });
  process.stdout.write(`${report}\n`);
  expect(Math.max(...durations)).toBeLessThan(TARGET_MS);
});
