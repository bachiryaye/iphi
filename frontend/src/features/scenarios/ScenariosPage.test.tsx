import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { statusReadOnly } from "@/test/apiFixtures";
import { renderApp, requests, seriousViolations, stubApi } from "@/test/render";

const run = {
  id: "run-12",
  number: 12,
  scenario_key: "collector_down",
  target_component_key: "collector-01",
  parameters: {},
  seed: 42,
  source: "simulation",
  started_at: "2026-11-12T10:39:37Z",
  started_by: "local-dev",
  status: "active",
  ends_at: null,
  stopped_at: null,
};

describe("Scenarios", () => {
  it("lists fault scenarios with their expected outcome", async () => {
    stubApi();
    renderApp("/scenarios");

    const card = await screen.findByRole("region", { name: "Collector down" });
    expect(card).toHaveTextContent("Critical within 10 s (R-AVAIL-001)");
    expect(card).toHaveTextContent("one availability incident");
    expect(screen.queryByRole("region", { name: "Baseline" })).not.toBeInTheDocument();
  });

  it("starts a scenario on its default target", async () => {
    const fetch = stubApi();
    renderApp("/scenarios");

    const card = await screen.findByRole("region", { name: "Collector down" });
    expect(await within(card).findByLabelText("Target")).toHaveValue("collector-01");
    await userEvent.click(within(card).getByRole("button", { name: "Start scenario" }));

    expect(requests(fetch)).toContain("POST /api/v1/simulations/scenarios");
  });

  it("stops an active run", async () => {
    const fetch = stubApi({
      "/api/v1/simulations/runs": { body: { items: [run], next_cursor: null } },
      "/api/v1/simulations/runs/:id/stop": { body: { ...run, status: "stopped" } },
    });
    renderApp("/scenarios");

    const runs = await screen.findByRole("region", { name: "Active scenario runs" });
    await userEvent.click(await within(runs).findByRole("button", { name: "Stop" }));

    expect(requests(fetch)).toContain("POST /api/v1/simulations/runs/run-12/stop");
  });

  it("asks for confirmation in the page before a reset", async () => {
    stubApi();
    renderApp("/scenarios");

    await userEvent.click(await screen.findByRole("button", { name: "Reset…" }));

    expect(screen.getByRole("group", { name: "Confirm reset" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Confirm reset" })).toBeEnabled();
  });

  it("disables controls and says why when mutations are refused", async () => {
    stubApi({ "/api/v1/system/status": { body: statusReadOnly } });
    renderApp("/scenarios");

    expect(await screen.findByText(/Read-only: Mutations are disabled/)).toBeVisible();
    await screen.findByRole("region", { name: "Collector down" });
    expect(
      screen
        .getAllByRole("button", { name: "Start scenario" })
        .every((button) => button.hasAttribute("disabled")),
    ).toBe(true);
    expect(screen.getByRole("button", { name: "Reset…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^realtime$/ })).toBeDisabled();
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp("/scenarios");
    await screen.findByRole("region", { name: "Collector down" });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
