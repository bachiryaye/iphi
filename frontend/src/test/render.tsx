import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { LanguageProvider } from "@/shared/i18n/LanguageProvider";

import { routes } from "@/app/routes";
import { setCsrfToken } from "@/shared/api/client";
import type { Session } from "@/shared/identity/session";

export const sessionFixture: Session = {
  user: { username: "admin", display_name: "Demo admin", role: "admin" },
  csrf_token: "test-only-csrf",
  expires_at: "2099-01-01T00:00:00Z",
};

import {
  activeIncidents,
  clock,
  collectorDetail,
  collectorRules,
  components,
  diagnostic,
  incidentDetail,
  logs,
  platform,
  rules,
  scenarios,
  statusMutable,
  topology,
  upSeries,
  recordedHistory,
} from "./apiFixtures";
import { readyBody } from "./fixtures";

export function renderApp(
  path = "/",
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  authenticated = true,
) {
  if (authenticated && client.getQueryData(["session"]) === undefined) {
    client.setQueryData(["session"], sessionFixture);
    setCsrfToken(sessionFixture.csrf_token);
  }
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <RouterProvider router={router} />
      </LanguageProvider>
    </QueryClientProvider>,
  );
}

export interface Reply {
  status?: number;
  body: unknown;
  headers?: Record<string, string>;
}

export type Routes = Record<string, Reply | "unreachable">;

/** The API of the collector_down fixture: every view finds its endpoint answered. */
export const defaultRoutes: Routes = {
  "/api/v1/auth/me": { body: sessionFixture },
  "/ready": { body: readyBody },
  "/api/v1/platforms": { body: { items: [platform] } },
  "/api/v1/platforms/:id/topology": { body: topology },
  "/api/v1/components": { body: { items: components } },
  "/api/v1/components/:id": { body: collectorDetail },
  "/api/v1/components/:id/health": { body: collectorRules },
  "/api/v1/components/:id/state-history": { body: recordedHistory },
  "/api/v1/rule-evaluations": {
    body: { environment: "simulation", items: [collectorDetail.reason], next_cursor: null },
  },
  "/api/v1/health-rules": { body: rules },
  "/api/v1/metrics": { body: upSeries },
  "/api/v1/logs": { body: logs },
  "/api/v1/incidents": { body: activeIncidents },
  "/api/v1/incidents/:id": { body: incidentDetail },
  "/api/v1/incidents/:id/diagnostics": { body: { items: [diagnostic] } },
  "/api/v1/system/status": { body: statusMutable },
  "/api/v1/simulations/scenarios": { body: scenarios },
  "/api/v1/simulations/runs": { body: { items: [], next_cursor: null } },
  "/api/v1/simulations/clock": { body: clock },
};

function match(routes: Routes, path: string): Reply | "unreachable" | undefined {
  for (const [pattern, reply] of Object.entries(routes)) {
    const regex = new RegExp(`^${pattern.replace(/:[a-z]+/g, "[^/]+")}$`);
    if (regex.test(path)) return reply;
  }
  return undefined;
}

const notFound: Reply = {
  status: 404,
  body: {
    type: "about:blank",
    title: "Not Found",
    status: 404,
    detail: "No such route.",
    code: "NOT_FOUND",
    correlation_id: null,
    errors: [],
  },
};

/**
 * Answers by path; `overrides` replace single routes (exact keys first, so a test can pin one
 * endpoint). Every request is recorded on the returned mock.
 */
export function stubApi(overrides: Routes = {}) {
  const routes = { ...overrides, ...defaultRoutes, ...overrides };
  const fetch = vi.fn((input: Request | string) => {
    const request = typeof input === "string" ? new Request(input) : input;
    const reply = match(routes, new URL(request.url).pathname) ?? notFound;
    if (reply === "unreachable") return Promise.reject(new TypeError("Failed to fetch"));
    return Promise.resolve(
      new Response(JSON.stringify(reply.body), {
        status: reply.status ?? 200,
        headers: { "content-type": "application/json", ...reply.headers },
      }),
    );
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

/** Method and path of each recorded request, for asserting on mutations. */
export function requests(fetch: ReturnType<typeof stubApi>) {
  return fetch.mock.calls.map(([input]) => {
    const request = typeof input === "string" ? new Request(input) : input;
    return `${request.method} ${new URL(request.url).pathname}`;
  });
}

export function stubUnreachable() {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
  );
}

/** design system §9: no serious or critical axe violation. Contrast is verified on tokens. */
export async function seriousViolations(container: HTMLElement) {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help}`);
}
