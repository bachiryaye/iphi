import { expect, type Locator, type Page } from "@playwright/test";
import createClient from "openapi-fetch";

import type { components, paths } from "../src/shared/api/schema";
import type {
  Clock,
  Component,
  HealthState,
  Incident,
  IncidentDetail,
  Platform,
  ScenarioCatalog,
  ScenarioKey,
  ScenarioRun,
} from "../src/shared/api/types";

type Schemas = components["schemas"];

export const BASE_URL = process.env.IPHI_E2E_URL ?? "http://127.0.0.1:8081";
export const VIEWPORT = { width: 1440, height: 900 };

/** A reset purges the simulated history under the clock lock. */
const RESET_TIMEOUT_MS = 120_000;
/** One worker cycle (5 s) plus one view refresh (10 s), with margin. */
export const SEEN = 45_000;

interface Result<T> {
  data?: T;
  response: Response;
}

function body<T>({ data, response }: Result<T>): T {
  if (data === undefined) {
    throw new Error(`${response.url} answered ${String(response.status)}`);
  }
  return data;
}

/** Public API through the generated contract: same routes and mutation guard as the UI. */
export class Simulation {
  private readonly api = createClient<paths>({ baseUrl: BASE_URL });

  async reset(seed?: number): Promise<Schemas["ResetOut"]> {
    return body(
      await this.api.POST("/api/v1/simulations/reset", {
        body: seed === undefined ? {} : { seed },
        signal: AbortSignal.timeout(RESET_TIMEOUT_MS),
      }),
    );
  }

  /** Clock changes before the first evaluations after a reset leave slots unevaluated (ADR 0019). */
  async waitAllHealthy(timeout = SEEN): Promise<void> {
    const total = (await this.components()).length;
    await expect
      .poll(async () => (await this.platform()).health.counts.healthy, { timeout })
      .toBe(total);
  }

  private async clock(command: Schemas["SetClockModeIn"] | Schemas["AdvanceClockIn"]) {
    return body(await this.api.POST("/api/v1/simulations/clock", { body: command }));
  }

  accelerate(speed: number): Promise<Clock> {
    return this.clock({ action: "set_mode", mode: "accelerated", speed });
  }

  manualClock(): Promise<Clock> {
    return this.clock({ action: "set_mode", mode: "manual" });
  }

  advance(seconds: number): Promise<Clock> {
    return this.clock({ action: "advance", seconds });
  }

  async platformTime(): Promise<number> {
    return Date.parse(body(await this.api.GET("/api/v1/simulations/clock")).platform_time);
  }

  async waitPlatformSeconds(seconds: number, timeout: number): Promise<void> {
    const until = (await this.platformTime()) + seconds * 1000;
    await expect.poll(() => this.platformTime(), { timeout }).toBeGreaterThanOrEqual(until);
  }

  async start(scenario_key: ScenarioKey, parameters: Record<string, number> = {}) {
    return body(
      await this.api.POST("/api/v1/simulations/scenarios", { body: { scenario_key, parameters } }),
    );
  }

  async stop(run: ScenarioRun): Promise<ScenarioRun> {
    return body(
      await this.api.POST("/api/v1/simulations/runs/{run_id}/stop", {
        params: { path: { run_id: run.id } },
        headers: { "content-type": "application/json" },
      }),
    );
  }

  async components(): Promise<Component[]> {
    return body(await this.api.GET("/api/v1/components")).items;
  }

  async component(key: string): Promise<Component> {
    const found = (await this.components()).find((c) => c.key === key);
    if (found === undefined) throw new Error(`no component ${key}`);
    return found;
  }

  async platform(): Promise<Platform> {
    const platform = body(await this.api.GET("/api/v1/platforms")).items[0];
    if (platform === undefined) throw new Error("no platform seeded");
    return platform;
  }

  async activeIncidents(): Promise<Incident[]> {
    const page = await this.api.GET("/api/v1/incidents", {
      params: { query: { status: ["open", "acknowledged"], limit: 100 } },
    });
    return body(page).items;
  }

  async incident(id: string): Promise<IncidentDetail> {
    return body(
      await this.api.GET("/api/v1/incidents/{incident_id}", {
        params: { path: { incident_id: id } },
      }),
    );
  }

  async diagnose(
    incidentId: string,
    mode: "deterministic" | "llm" = "deterministic",
  ): Promise<Schemas["DiagnosticOut"]> {
    return body(
      await this.api.POST("/api/v1/incidents/{incident_id}/diagnose", {
        params: { path: { incident_id: incidentId }, query: { mode } },
        headers: { "content-type": "application/json" },
      }),
    );
  }

  /** Oldest first. */
  async ruleStates(componentId: string, ruleKey: string, from: string): Promise<HealthState[]> {
    const page = await this.api.GET("/api/v1/rule-evaluations", {
      params: { query: { component_id: componentId, rule_key: ruleKey, from, limit: 200 } },
    });
    return body(page)
      .items.toSorted((a, b) => a.id - b.id)
      .map((evaluation) => evaluation.state);
  }

  async scenarios(): Promise<ScenarioCatalog> {
    return body(await this.api.GET("/api/v1/simulations/scenarios"));
  }

  async readiness(): Promise<Schemas["ReadinessOut"]> {
    return body(await this.api.GET("/ready"));
  }

  async systemStatus(): Promise<Schemas["SystemStatusOut"]> {
    return body(await this.api.GET("/api/v1/system/status"));
  }
}

export function tableRow(page: Page, region: string | RegExp, header: RegExp): Locator {
  return page
    .getByRole("region", { name: region })
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: header }) });
}

export function componentRow(page: Page, key: string): Locator {
  return tableRow(page, "Components", new RegExp(`^${key}`));
}

export function activeIncidents(page: Page): Locator {
  return page.getByRole("region", { name: /Active incidents/ });
}

export function incidentLink(page: Page, name: RegExp = /INC-/): Locator {
  return activeIncidents(page).getByRole("link", { name });
}

export function platformState(page: Page): Locator {
  return page.getByRole("group", { name: "Platform state" });
}

export async function openOverview(page: Page): Promise<void> {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("note")).toContainText("SIMULATED DATA");
}
