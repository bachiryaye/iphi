import { expect, test } from "@playwright/test";

import {
  componentRow,
  incidentLink,
  openOverview,
  platformState,
  SEEN,
  Simulation,
  tableRow,
} from "./simulation";

/** Mandatory scenarios of the backlog §01.1. Rules follow platform time, so FAST changes no outcome. */
const FAST = 30;
const SLOW = 90_000;
/** Well past every rule window. */
const STABLE_S = 600;

const simulation = new Simulation();

test.beforeEach(async () => {
  await simulation.reset();
  await simulation.waitAllHealthy();
});

test.afterAll(async () => {
  await simulation.reset();
});

test("1. collector down: Critical, one incident with evidence, deterministic diagnosis", async ({
  page,
}) => {
  await page.goto("/scenarios", { waitUntil: "domcontentloaded" });
  const scenario = page.getByRole("region", { name: "Collector down" });
  await expect(scenario).toContainText("One availability incident on the target");
  await scenario.getByRole("button", { name: "Start scenario" }).click();
  await expect(
    page.getByRole("region", { name: "Active scenario runs" }).getByRole("row", {
      name: /collector_down/,
    }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Overview" }).click();
  const collector = componentRow(page, "collector-01");
  await expect(collector).toContainText("Critical", { timeout: SEEN });
  // Just after a reset R-CONN-001 may decide before R-AVAIL-001 (ADR 0017).
  await expect(collector).toContainText(/DOWN since|% of probes answered/);
  await expect(platformState(page)).toContainText("Critical");

  const incident = incidentLink(page, /collector-01 unreachable/);
  await expect(incident).toHaveCount(1, { timeout: SEEN });
  await expect(incidentLink(page)).toHaveCount(1);

  await incident.click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("collector-01 unreachable");
  await expect(page.getByRole("region", { name: "Evidence chain" })).toContainText("R-AVAIL-001");

  const diagnosis = page.getByRole("region", { name: /^Diagnosis/ });
  await expect(diagnosis).toContainText("It needs no AI provider");
  await page.getByRole("button", { name: "Diagnose" }).click();
  await expect(page.getByRole("region", { name: "Diagnosis: deterministic" })).toContainText(
    "causation is not proven",
  );
});

test("2. latency rise: Warning, then Critical, then a stable recovery", async ({ page }) => {
  await simulation.accelerate(FAST);
  const run = await simulation.start("latency_rise");
  await openOverview(page);

  const gateway = componentRow(page, "edge-gateway-01");
  await expect(gateway).toContainText("Critical", { timeout: SLOW });
  await expect(gateway).toContainText("probe latency");
  await expect(incidentLink(page, /edge-gateway-01/)).toHaveCount(1, { timeout: SEEN });

  // At this speed Warning can fall between two refreshes; the stored evaluations keep it.
  const [opened] = await simulation.activeIncidents();
  expect(opened?.failure_class).toBe("latency");
  expect(opened?.peak_severity).toBe("critical");
  const gatewayId = (await simulation.component("edge-gateway-01")).id;
  const raised = await simulation.ruleStates(gatewayId, "R-LAT-001", run.started_at);
  expect(raised.indexOf("warning")).toBeGreaterThanOrEqual(0);
  expect(raised.lastIndexOf("critical")).toBeGreaterThan(raised.indexOf("warning"));

  await simulation.stop(run);
  await expect(gateway).toContainText("Healthy", { timeout: SLOW });
  await expect(page.getByRole("region", { name: /Active incidents/ })).toContainText(
    "No active incidents.",
    { timeout: SEEN },
  );
  await simulation.waitPlatformSeconds(STABLE_S, SLOW);
  const states = await simulation.ruleStates(gatewayId, "R-LAT-001", run.started_at);
  const recovered = states.indexOf("healthy", states.lastIndexOf("critical"));
  expect(recovered).toBeGreaterThan(0);
  expect(states.slice(recovered).every((state) => state === "healthy")).toBe(true);
  await expect(gateway).toContainText("Healthy");
  expect(await simulation.activeIncidents()).toHaveLength(0);
  const resolved = await simulation.incident(opened?.id ?? "");
  expect(resolved.status).toBe("resolved");
  expect(resolved.reopen_count).toBe(0);
});

test("3. stale data while the service answers: freshness, distinct from availability", async ({
  page,
}) => {
  await simulation.accelerate(FAST);
  await simulation.start("stale_data");
  await openOverview(page);

  const historian = componentRow(page, "historian-01");
  await expect(historian).toContainText("Critical", { timeout: SLOW });
  await expect(historian).toContainText("data age");
  await expect(incidentLink(page, /historian-01 process data stale/)).toHaveCount(1, {
    timeout: SEEN,
  });
  await expect(incidentLink(page, /unreachable/)).toHaveCount(0);

  await historian.getByRole("link", { name: /^historian-01/ }).click();
  await expect(tableRow(page, "Rules", /R-AVAIL-001/)).toContainText("Healthy");
  await expect(tableRow(page, "Rules", /R-FRESH-001/)).toContainText("Critical");
});

test("4. no observation at all: Unknown, never Healthy", async ({ page }) => {
  await simulation.start("telemetry_blackout");
  await openOverview(page);

  const historian = componentRow(page, "historian-01");
  await expect(historian).toContainText("Unknown", { timeout: SEEN });
  await expect(historian).not.toContainText("Healthy");
  await expect(platformState(page)).toContainText("Unknown");
  await expect(incidentLink(page, /historian-01 telemetry lost/)).toHaveCount(1, {
    timeout: SEEN,
  });
});

test("5. repeated errors: one incident with growing occurrences, no storm", async ({ page }) => {
  await simulation.accelerate(FAST);
  await simulation.start("error_burst");
  await openOverview(page);

  const incident = incidentLink(page, /data-api-01 errors/);
  await expect(incident).toHaveCount(1, { timeout: SEEN });
  await expect
    .poll(async () => (await simulation.activeIncidents())[0]?.occurrence_count ?? 0, {
      timeout: SEEN,
    })
    .toBeGreaterThanOrEqual(20);

  expect(await simulation.activeIncidents()).toHaveLength(1);
  await expect(incidentLink(page)).toHaveCount(1);

  await incident.click();
  await expect(page.getByRole("region", { name: "Timeline" })).toContainText(
    /\d+ occurrences grouped/,
  );
});

test("6. no AI provider: monitoring, incidents and the dashboard keep working", async ({
  page,
}) => {
  const readiness = await simulation.readiness();
  expect(readiness.status).toBe("ready");
  expect(readiness.checks.find((check) => check.name === "ai_provider")?.status).toBe("disabled");

  await simulation.start("collector_down");
  await openOverview(page);
  await expect(tableRow(page, "Monitor readiness", /AI/)).toContainText(
    "deterministic diagnosis only",
  );
  await expect(componentRow(page, "collector-01")).toContainText("Critical", { timeout: SEEN });
  await expect(incidentLink(page, /collector-01 unreachable/)).toHaveCount(1, { timeout: SEEN });
  await expect(page.getByRole("group", { name: "Monitor status" })).not.toContainText("stalled");
  const [incident] = await simulation.activeIncidents();
  if (incident === undefined) throw new Error("No incident detected.");
  const attempt = await simulation.diagnose(incident.id, "llm");
  expect(attempt.error_code).toBe("LLM_DISABLED");
  expect(attempt.deterministic_id).not.toBeNull();
  await page.goto(`/incidents/${incident.id}`);
  await expect(page.getByRole("region", { name: "Diagnosis: deterministic" })).toBeVisible();
  await expect(page.getByText("Monitor running", { exact: true })).toBeVisible();
});

/** Conclusions without the identifiers and timestamps of one run. */
async function conclusions(simulation: Simulation) {
  const components = await simulation.components();
  const incidents = await simulation.activeIncidents();
  return {
    platform: (await simulation.platform()).health.rationale,
    components: components
      .map((c) => ({
        key: c.key,
        state: c.health.state,
        rule: c.reason?.rule.key ?? null,
        impacted_by: c.impacted_by.map((ref) => ref.key).sort(),
      }))
      .sort((a, b) => a.key.localeCompare(b.key)),
    incidents: incidents.map((i) => ({
      title: i.title,
      failure_class: i.failure_class,
      severity: i.severity,
      impacted: i.impacted.map((impact) => impact.component.key).sort(),
    })),
  };
}

test("8. seeded clean environment: the same fault leads to the same conclusions", async () => {
  const scenarios = await simulation.scenarios();
  expect(scenarios.items).toHaveLength(9);

  const replay = async () => {
    const reset = await simulation.reset(42);
    expect(reset.clock.seed).toBe(42);
    expect(reset.baseline_run.scenario_key).toBe("baseline");
    expect(await simulation.components()).toHaveLength(7);
    await simulation.waitAllHealthy();
    // Five nominal minutes fill every rule window identically in both replays.
    await simulation.manualClock();
    await simulation.advance(300);
    await simulation.start("collector_down");
    const clock = await simulation.advance(180);
    const slotMs = clock.sample_interval_s * 1000;
    const target = Date.parse(clock.platform_time);
    await expect
      .poll(async () => Date.parse((await simulation.platform()).health.evaluated_at ?? ""), {
        timeout: SEEN,
      })
      .toBe(target - (target % slotMs));
    return conclusions(simulation);
  };

  const first = await replay();
  expect(first.incidents).toEqual([
    {
      title: "collector-01 unreachable",
      failure_class: "availability",
      severity: "critical",
      impacted: ["analytics-01", "historian-01"],
    },
  ]);
  expect(await replay()).toEqual(first);
});
