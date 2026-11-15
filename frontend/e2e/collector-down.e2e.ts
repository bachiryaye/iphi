import { expect, type APIRequestContext, test } from "@playwright/test";

const JSON_HEADERS = { "content-type": "application/json" };

async function reset(request: APIRequestContext) {
  const response = await request.post("/api/v1/simulations/reset", {
    headers: JSON_HEADERS,
    data: {},
  });
  expect(response.status(), await response.text()).toBe(200);
}

test.afterEach(async ({ request }) => {
  await reset(request);
});

test("collector_down turns collector-01 Critical and lists one incident", async ({
  page,
  request,
}) => {
  await reset(request);
  const started = await request.post("/api/v1/simulations/scenarios", {
    headers: JSON_HEADERS,
    data: { scenario_key: "collector_down", target_component_key: "collector-01", parameters: {} },
  });
  expect(started.status(), await started.text()).toBe(201);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("note")).toContainText("SIMULATED DATA");

  const components = page.getByRole("region", { name: "Components" });
  const collector = components.getByRole("row").filter({
    has: page.getByRole("rowheader", { name: /^collector-01/ }),
  });
  // Two failed probes at 5 s, then the 10 s view refresh.
  await expect(collector).toContainText("Critical", { timeout: 45_000 });
  // Right after a reset the 300 s connectivity window is nearly empty, so R-CONN-001 may be the
  // rule behind the state before R-AVAIL-001 (ADR 0017): either reading names the outage.
  await expect(collector).toContainText(/DOWN since|0 % of probes answered/);

  const incidents = page.getByRole("region", { name: /Active incidents/ });
  await expect(incidents.getByRole("link", { name: /collector-01 unreachable/ })).toHaveCount(1, {
    timeout: 30_000,
  });
  await expect(page.getByRole("group", { name: "Platform state" })).toContainText("Critical");

  await incidents.getByRole("link", { name: /collector-01 unreachable/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("collector-01 unreachable");
  await expect(page.getByRole("region", { name: "Evidence chain" })).toContainText("R-AVAIL-001");
});
