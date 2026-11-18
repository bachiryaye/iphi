import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { COLLECTOR_ID, collectorDetail } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

const path = `/components/${COLLECTOR_ID}`;

describe("Component", () => {
  it("never explains a component without evaluations as every rule Healthy", async () => {
    stubApi({
      [`/api/v1/components/${COLLECTOR_ID}`]: {
        body: {
          ...collectorDetail,
          reason: null,
          health: {
            state: "unknown",
            evaluated_state: null,
            since: null,
            evaluated_at: null,
            stale: true,
            stale_reason: "Not evaluated yet.",
          },
        },
      },
    });
    renderApp(path);
    await screen.findByRole("heading", { level: 1, name: "collector-01" });
    const reason = screen.getByText("Reason", { selector: "dt" }).parentElement;
    expect(reason).toHaveTextContent("Not evaluated yet.");
    expect(reason).not.toHaveTextContent("every rule Healthy");
  });
  it("heads with state, reason rule and the open incident as the primary action", async () => {
    stubApi();
    renderApp(path);

    expect(
      await screen.findByRole("heading", { level: 1, name: "collector-01" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Reason", { selector: "dt" }).parentElement).toHaveTextContent(
      "R-AVAIL-001 v1 last(up, 10 s) = 0 < 1: probe not answered.",
    );
    expect(await screen.findByRole("link", { name: "Open incident INC-0007" })).toHaveAttribute(
      "href",
      expect.stringContaining("/incidents/"),
    );
  });

  it("justifies every rule and keeps a rule without samples Unknown", async () => {
    stubApi();
    renderApp(path);

    const rules = await screen.findByRole("region", { name: "Rules" });
    const latency = (await within(rules).findByRole("rowheader", { name: /R-LAT-001/ })).closest(
      "tr",
    );
    expect(latency).toHaveTextContent("Unknown");
    expect(latency).toHaveTextContent("no samples");
    expect(rules).toHaveTextContent("It is never counted as Healthy.");
  });

  it("draws the metric with a text alternative and a table view", async () => {
    stubApi();
    renderApp(path);

    const panel = await screen.findByRole("region", { name: "Metric history" });
    const chart = await within(panel).findByRole("img", { name: /^up for collector-01/ });
    expect(chart).toHaveAccessibleName(/1 gap without data/);
    await userEvent.click(within(panel).getByRole("button", { name: "View as table" }));
    expect(within(panel).getByRole("table", { name: "Latest values of up" })).toBeInTheDocument();
  });

  it("groups repeated logs by fingerprint", async () => {
    stubApi();
    renderApp(path);

    const logs = await screen.findByRole("region", { name: "Recent logs" });
    const rows = await within(logs).findAllByRole("row");
    expect(rows).toHaveLength(2);
    expect(rows[1]).toHaveTextContent("connection refused by upstream gateway3a91c4e02");
  });

  it("lists upstream and downstream components", async () => {
    stubApi();
    renderApp(path);

    const deps = await screen.findByRole("region", { name: "Dependencies" });
    expect(within(deps).getByRole("region", { name: "Upstream" })).toHaveTextContent(
      "edge-gateway-01",
    );
    expect(within(deps).getByRole("region", { name: "Downstream" })).toHaveTextContent(
      "historian-01",
    );
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp(path);
    await screen.findByRole("region", { name: "Recent logs" });
    await screen.findByRole("img", { name: /^up for collector-01/ });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
