import { expect, test } from "@playwright/test";

import { componentRow, incidentLink, SEEN, Simulation } from "./simulation";

test("US-12: MQTT observations drive the existing dashboard and evidence", async ({
  page,
}, testInfo) => {
  test.skip(process.env.IPHI_E2E_MQTT !== "1", "Requires the optional MQTT Compose profile");
  const simulation = new Simulation();
  await simulation.reset();
  try {
    await simulation.waitAllHealthy();
    const status = await simulation.systemStatus();
    expect(status.collection.connectors.map((c) => c.connector_key)).toEqual(["mqtt"]);

    await page.goto("/scenarios", { waitUntil: "domcontentloaded" });
    await page
      .getByRole("region", { name: "Collector down" })
      .getByRole("button", { name: "Start scenario" })
      .click();
    await expect(
      page.getByRole("region", { name: "Active scenario runs" }).getByRole("row", {
        name: /collector_down/,
      }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Overview" }).click();
    await expect(componentRow(page, "collector-01")).toContainText("Critical", {
      timeout: SEEN,
    });
    const link = incidentLink(page, /collector-01 unreachable/);
    await expect(link).toHaveCount(1, { timeout: SEEN });
    await expect(incidentLink(page)).toHaveCount(1);
    await link.click();
    await expect(page.getByRole("region", { name: "Evidence chain" })).toContainText("R-AVAIL-001");
    const incidents = await simulation.activeIncidents();
    expect(incidents).toHaveLength(1);
    const incident = incidents[0];
    if (incident === undefined) throw new Error("MQTT incident missing");
    const detail = await simulation.incident(incident.id);
    expect(detail.source).toBe("mqtt");
    expect(detail.environment).toBe("simulation");
    expect(
      detail.evidence.some(
        (item) =>
          item.sample?.source === "mqtt" &&
          item.sample.metric_name === "up" &&
          item.sample.value === 0,
      ),
    ).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("mqtt-incident.png"), fullPage: true });
  } finally {
    await simulation.reset();
  }
});
