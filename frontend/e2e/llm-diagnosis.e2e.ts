import { expect, test } from "@playwright/test";

import { SEEN, Simulation } from "./simulation";

test("US-08: fake provider, clickable evidence and deterministic comparison", async ({ page }) => {
  test.skip(process.env.IPHI_E2E_LLM !== "fake", "Set IPHI_E2E_LLM=fake on a fake-provider stack.");
  const simulation = new Simulation();
  expect((await simulation.systemStatus()).ai_provider.detail).toContain("fake");
  await simulation.reset();
  await simulation.waitAllHealthy();
  try {
    await simulation.start("collector_down");
    await expect.poll(() => simulation.activeIncidents(), { timeout: SEEN }).toHaveLength(1);
    const [incident] = await simulation.activeIncidents();
    if (incident === undefined) throw new Error("No incident detected.");
    await page.goto(`/incidents/${incident.id}`);
    await page.getByRole("button", { name: "AI diagnosis", exact: true }).click();
    const ai = page.getByRole("region", { name: "Diagnosis: AI" });
    await expect(ai).toContainText("AI-generated — verify against evidence");
    await expect(ai).toContainText("fake/evidence-v1");
    await expect(ai).toContainText("Local test provider; no language model called");
    const citation = ai.getByRole("button", { name: /^Evidence E/ }).first();
    await citation.click();
    await expect(citation).toHaveAttribute("aria-pressed", "true");
    await page.getByText("Compare with deterministic diagnosis").click();
    await expect(page.getByRole("region", { name: "Diagnosis: deterministic" })).toContainText(
      "causation is not proven",
    );
    await expect(page.getByText("Monitor running", { exact: true })).toBeVisible();
  } finally {
    await simulation.reset();
  }
});
