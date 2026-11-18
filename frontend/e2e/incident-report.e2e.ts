import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { SEEN, Simulation } from "./simulation";

test("US-09: download PDF and CSV from the incident evidence", async ({ page }) => {
  const simulation = new Simulation();
  await simulation.reset();
  await simulation.waitAllHealthy();
  try {
    await simulation.start("collector_down");
    await expect
      .poll(
        async () =>
          (await simulation.activeIncidents()).map((item) => [item.failure_class, item.severity]),
        { timeout: SEEN },
      )
      .toEqual([["availability", "critical"]]);
    const [incident] = await simulation.activeIncidents();
    if (incident === undefined) throw new Error("No incident detected.");
    await page.goto(`/incidents/${incident.id}`);
    await page.getByRole("button", { name: "Diagnose", exact: true }).click();
    await expect(page.getByRole("region", { name: "Diagnosis: deterministic" })).toBeVisible();
    for (const format of ["pdf", "csv"] as const) {
      const downloading = page.waitForEvent("download");
      await page.getByRole("button", { name: `Export ${format.toUpperCase()}` }).click();
      const download = await downloading;
      expect(download.suggestedFilename()).toBe(`IPHI-${incident.reference}-simulated.${format}`);
      const path = await download.path();
      const bytes = await readFile(path);
      if (format === "pdf") expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
      else {
        const output = bytes.toString();
        expect(output).toContain('"simulation"');
        expect(output).toContain('"evidence"');
        expect(output).toContain('"event"');
        expect(output).toContain('"deterministic"');
        expect(output).toContain("R-AVAIL-001");
      }
    }
    await expect(page.getByText("Monitor running", { exact: true })).toBeVisible();
  } finally {
    await simulation.reset();
  }
});
