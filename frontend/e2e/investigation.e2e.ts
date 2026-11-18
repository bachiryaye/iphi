import { expect, test } from "@playwright/test";

import { Simulation, SEEN, componentRow } from "./simulation";

test("committed health updates display within two seconds; disconnected polling and reconnect resynchronize", async ({
  page,
  context,
}) => {
  test.setTimeout(180_000);
  const sim = new Simulation();
  await sim.reset();
  await sim.waitAllHealthy();
  const collector = await sim.component("collector-01");
  const connection = await context.newCDPSession(page);
  await connection.send("Network.enable");
  const received = { at: 0, count: 0 };
  connection.on("Network.eventSourceMessageReceived", (event) => {
    const value: unknown = JSON.parse(event.data);
    if (
      typeof value === "object" &&
      value !== null &&
      "id" in value &&
      value.id === collector.id &&
      event.eventName === "component.health_changed"
    ) {
      received.at = Date.now();
      received.count += 1;
    }
  });
  await page.goto("/");
  await expect(page.getByText("Connecting live updates…", { exact: false })).toHaveCount(0);
  const row = componentRow(page, "collector-01");
  await expect(row).toContainText("Healthy");
  const run = await sim.start("collector_down");
  await expect(row).toContainText("Critical", { timeout: SEEN });
  expect(received.count, "a committed component transition reached EventSource").toBeGreaterThan(0);
  expect(Date.now() - received.at, "notification received to visible Critical").toBeLessThan(2000);
  console.log(`US-07 committed update display: ${String(Date.now() - received.at)} ms`);

  const stream = "**/api/v1/events/stream";
  await page.route(stream, (route) => route.abort("failed"));
  await context.setOffline(true);
  await expect(page.getByText("Live updates paused.", { exact: false })).toBeVisible();
  await context.setOffline(false);
  await sim.stop(run);
  await sim.reset();
  await sim.waitAllHealthy();
  await expect(row).toContainText("Healthy", { timeout: 35_000 });
  await expect(
    page.getByText("This page refreshes every 30 s meanwhile.", { exact: false }),
  ).toBeVisible();

  await sim.manualClock();
  await sim.start("collector_down");
  await sim.advance(30);
  await expect
    .poll(async () => (await sim.component("collector-01")).health.state, { timeout: SEEN })
    .toBe("critical");
  await page.unroute(stream);
  const resumedAt = Date.now();
  await page.getByRole("button", { name: "Retry live updates" }).click();
  await expect(row).toContainText("Critical", { timeout: 2000 });
  await expect(page.getByRole("button", { name: "Retry live updates" })).toHaveCount(0);
  console.log(`US-07 reconnect resync: ${String(Date.now() - resumedAt)} ms`);
  await connection.detach();
  await sim.reset();
});

test("keyboard topology selection, recorded health and an audited investigation comment", async ({
  page,
}) => {
  const sim = new Simulation();
  await sim.reset();
  await sim.waitAllHealthy();
  await sim.start("collector_down");
  await expect
    .poll(
      async () =>
        (await sim.activeIncidents()).filter((i) => i.failure_class === "availability").length,
      { timeout: SEEN },
    )
    .toBe(1);
  const collector = await sim.component("collector-01");
  await page.goto("/topology");
  const node = page.locator(".react-flow__node").filter({ hasText: "collector-01" });
  await node.focus();
  await node.press("Enter");
  const details = page.getByRole("complementary", { name: "Selected component" });
  await expect(details).toContainText("collector-01");
  await expect(page).toHaveURL(new RegExp(`component=${collector.id}`));
  await details.getByRole("link", { name: "Investigate collector-01" }).click();
  const inspector = page.getByRole("slider", { name: "History time inspector" });
  await expect(inspector).toBeVisible();
  await inspector.focus();
  await inspector.press("End");
  await expect(inspector).toHaveAttribute("aria-valuetext", /UTC.*Critical/);
  await page.getByRole("button", { name: "View states as table" }).click();
  await expect(page.getByRole("table", { name: "Recorded state transitions" })).toContainText(
    "R-AVAIL-001",
  );
  const criticalRule = page
    .getByRole("table", { name: "Recorded state transitions" })
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: /^R-AVAIL-001/ }) })
    .filter({ hasText: "Critical" })
    .first();
  await criticalRule.getByRole("button").click();
  await expect(page.getByRole("table", { name: "Filtered stored evaluations" })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("evaluation")).toMatch(/^R-AVAIL-001\|/);
  await page.reload();
  await expect(page.getByRole("table", { name: "Filtered stored evaluations" })).toBeVisible();
  await expect(
    page
      .getByRole("img", { name: /up|probe|availability/i })
      .locator("svg")
      .first(),
  ).toBeVisible();
  await page.getByRole("link", { name: /Open incident/ }).click();
  const note = `Browser investigation ${String(Date.now())}: inspect collector input.`;
  await page.getByRole("textbox", { name: "Investigation comment" }).fill(note);
  await page.getByRole("button", { name: "Add comment" }).click();
  await expect(page.getByText(`“${note}”`)).toBeVisible();
  await page.reload();
  await expect(page.getByText(`“${note}”`)).toBeVisible();
});
