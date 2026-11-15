import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { topology } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

import { isImpactEdge, layoutTopology } from "./layout";

describe("topology layout", () => {
  it("orders components along the data flow and puts the database under the historian", () => {
    const placed = new Map(
      layoutTopology(topology.nodes, topology.edges).map((p) => [p.node.key, p]),
    );

    expect(
      [
        "plc-sim-01",
        "edge-gateway-01",
        "collector-01",
        "historian-01",
        "data-api-01",
        "analytics-01",
      ].map((key) => placed.get(key)?.column),
    ).toEqual([0, 1, 2, 3, 4, 5]);
    expect(placed.get("timeseries-db-01")).toMatchObject({ column: 3, row: 1 });
  });

  it("marks only the edges downstream of the failing collector as impact", () => {
    const nodes = new Map(topology.nodes.map((n) => [n.id, n]));
    const impact = topology.edges
      .filter((e) => isImpactEdge(e, nodes))
      .map((e) => nodes.get(e.dependent_id)?.key);

    expect(impact).toEqual(["historian-01", "data-api-01", "analytics-01"]);
  });
});

describe("Topology", () => {
  it("shows every component with its state, plus a text equivalent", async () => {
    stubApi();
    renderApp("/topology");

    const card = await screen.findByRole("region", { name: "Dependency chain" });
    const table = await within(card).findByRole("table", {
      name: "Components and their dependencies",
    });
    const historian = within(table).getByRole("rowheader", { name: "historian-01" }).closest("tr");
    expect(historian).toHaveTextContent("Warning");
    expect(historian).toHaveTextContent("collector-01 (data flow), timeseries-db-01 (runtime)");
    expect(card).toHaveTextContent("impact path from a Critical or Unknown component");
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp("/topology");
    await screen.findByRole("table", { name: "Components and their dependencies" });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
