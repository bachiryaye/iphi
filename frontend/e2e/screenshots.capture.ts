import { expect, test, type Browser, type Page } from "@playwright/test";

import {
  BASE_URL,
  componentRow,
  incidentLink,
  openOverview,
  SEEN,
  Simulation,
  VIEWPORT,
} from "./simulation";

/** README screenshots taken from the running stack (`make screenshots`). */
const OUTPUT = "../docs/design/screenshots";
const HISTORY_S = 20 * 60;
const THEMES = ["light", "dark"] as const;
const simulation = new Simulation();

/** The chart frame is visible while ECharts still loads; its SVG is the drawn chart. */
async function chartDrawn(page: Page, region: string | RegExp): Promise<void> {
  await expect(
    page.getByRole("region", { name: region }).getByRole("img").locator("svg").first(),
  ).toBeVisible();
}

interface View {
  name: string;
  open: (page: Page) => Promise<void>;
}

/** Hand-made contexts do not inherit the configuration's `use` options. */
async function capture(browser: Browser, views: readonly View[]): Promise<void> {
  for (const theme of THEMES) {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      colorScheme: theme,
      viewport: VIEWPORT,
    });
    const page = await context.newPage();
    for (const view of views) {
      await view.open(page);
      await page.screenshot({
        path: `${OUTPUT}/${view.name}-${theme}-1440.png`,
        animations: "disabled",
      });
    }
    await context.close();
  }
}

test("capture the dashboard during collector_down", async ({ browser }) => {
  test.setTimeout(300_000);
  await simulation.reset();
  await simulation.waitAllHealthy();
  await simulation.accelerate(60);
  await simulation.waitPlatformSeconds(HISTORY_S, 60_000);
  await simulation.accelerate(2);
  await simulation.start("collector_down");
  await expect
    .poll(async () => (await simulation.activeIncidents())[0]?.impacted.length ?? 0, {
      timeout: 120_000,
    })
    .toBeGreaterThanOrEqual(2);
  const [incident] = await simulation.activeIncidents();
  if (incident === undefined) throw new Error("fault not detected");
  await simulation.diagnose(incident.id);
  const collector = await simulation.component("collector-01");

  await capture(browser, [
    {
      name: "overview",
      open: async (page) => {
        await openOverview(page);
        await expect(componentRow(page, "collector-01")).toContainText("Critical", {
          timeout: SEEN,
        });
        await expect(incidentLink(page)).toHaveCount(1);
      },
    },
    {
      name: "incident",
      open: async (page) => {
        await page.goto(`/incidents/${incident.id}`);
        await expect(page.getByRole("region", { name: "Diagnosis: deterministic" })).toBeVisible();
        await chartDrawn(page, /^Signal/);
      },
    },
    {
      name: "topology",
      open: async (page) => {
        await page.goto("/topology");
        await expect(page.getByRole("heading", { level: 1 })).toContainText("Topology");
        await expect(page.getByText("collector-01").first()).toBeVisible();
      },
    },
    {
      name: "component",
      open: async (page) => {
        await page.goto(`/components/${collector.id}`);
        await expect(page.getByRole("region", { name: "Rules" })).toContainText("R-AVAIL-001");
        await chartDrawn(page, "Metric history");
      },
    },
  ]);

  await simulation.reset();
});
