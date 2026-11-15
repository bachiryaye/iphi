import { QueryClient } from "@tanstack/react-query";
import { act, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { healthyPlatform, noIncidents } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

const region = (name: string | RegExp) => screen.getByRole("region", { name });
const rowOf = (table: HTMLElement, key: string) =>
  within(table)
    .getByRole("rowheader", { name: new RegExp(`^${key}`) })
    .closest("tr");

describe("Overview", () => {
  it("is busy with static skeletons while loading", () => {
    stubApi();
    renderApp();

    expect(region("Platform health")).toHaveAttribute("aria-busy", "true");
  });

  it("states the platform state with the API's rationale and the component behind it", async () => {
    stubApi();
    renderApp();

    const health = region("Platform health");
    await within(health).findByText(/^Priority 1/);
    expect(health).toHaveTextContent(/Critical\s?since 10:39:47 UTC/);
    expect(health).toHaveTextContent(
      "Priority 1: a high-criticality component is Critical (collector-01).",
    );
    expect(within(health).getByRole("list", { name: "Components by state" })).toHaveTextContent(
      "Healthy4Warning1Critical1Unknown1",
    );
    expect(health).toHaveTextContent("3 components impacted:");
  });

  it("shows the failed collector as Critical with its outage, and the incident it opened", async () => {
    stubApi();
    renderApp();

    const table = await within(region("Components")).findByRole("table");
    const row = rowOf(table, "collector-01");
    expect(row).toHaveClass("row-critical");
    expect(row).toHaveTextContent("Critical");
    expect(row).toHaveTextContent("DOWN since 10:39:47 UTC");
    const incidents = region(/Active incidents/);
    expect(await within(incidents).findByRole("link", { name: /INC-0007/ })).toHaveAttribute(
      "href",
      "/incidents/0b6f1e1a-0000-4000-8000-000000000901",
    );
  });

  it("never shows a component without recent evidence as Healthy", async () => {
    stubApi();
    renderApp();

    const table = await within(region("Components")).findByRole("table");
    const row = rowOf(table, "analytics-01");
    expect(row).toHaveTextContent("Unknown");
    expect(row).not.toHaveTextContent("Healthy");
    expect(row).toHaveTextContent("no data");
  });

  it("explains an empty incident list without presenting it as a success", async () => {
    stubApi({
      "/api/v1/platforms": { body: { items: [healthyPlatform] } },
      "/api/v1/incidents": { body: noIncidents },
    });
    renderApp();

    const incidents = region(/Active incidents/);
    expect(await within(incidents).findByText("No active incidents.")).toBeInTheDocument();
    expect(within(incidents).getByRole("link", { name: "Open scenarios" })).toBeInTheDocument();
  });

  it("says what failed and what keeps working when components cannot load", async () => {
    stubApi({
      "/api/v1/components": {
        status: 500,
        body: {
          type: "about:blank",
          title: "Internal Server Error",
          status: 500,
          detail: "An internal error occurred.",
          code: "INTERNAL_ERROR",
          correlation_id: "c0ffee",
          errors: [],
        },
      },
    });
    renderApp();

    const alert = await within(region("Components")).findByRole("alert");
    expect(alert).toHaveTextContent("Could not load components.");
    expect(alert).toHaveTextContent("The API answered 500 INTERNAL_ERROR");
    expect(alert).toHaveTextContent("Detection continues on the server");
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("keeps the last data visible but marked stale once a refresh fails", async () => {
    stubApi();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderApp("/", client);
    await within(region("Components")).findByRole("table");

    stubApi({ "/api/v1/components": "unreachable" });
    await act(() => client.refetchQueries({ queryKey: ["components"] }));

    const components = region("Components");
    expect(await within(components).findByText(/refresh failed, retrying every 10/)).toBeVisible();
    expect(within(components).getByRole("table")).toBeInTheDocument();
  });

  it("carries the platform state in the top bar", async () => {
    stubApi();
    renderApp();

    const summary = await screen.findByRole("group", { name: "Platform state" });
    expect(summary).toHaveTextContent("Demo Plant Data Platform");
    expect(await within(summary).findByText("Critical")).toBeInTheDocument();
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp();
    await within(region("Components")).findByRole("table");

    expect(await seriousViolations(container)).toEqual([]);
  });
});
