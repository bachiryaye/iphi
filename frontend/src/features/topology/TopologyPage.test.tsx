import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { topology } from "@/test/apiFixtures";
import { renderApp, seriousViolations, stubApi } from "@/test/render";

import { isImpactEdge } from "./layout";
import { graphLayout } from "./graphLayout";

describe("topology layout", () => {
  it("places every dependency before its dependent without overlapping nodes", () => {
    const positions = graphLayout(topology);
    expect(positions.size).toBe(topology.nodes.length);
    for (const edge of topology.edges) {
      const source = positions.get(edge.dependency_id),
        target = positions.get(edge.dependent_id);
      if (source === undefined || target === undefined) throw new Error("Missing graph position");
      expect(source.x + 184).toBeLessThan(target.x);
    }
    expect(new Set([...positions.values()].map((p) => `${String(p.x)},${String(p.y)}`)).size).toBe(
      positions.size,
    );
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
