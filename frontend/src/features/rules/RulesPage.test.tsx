import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp, seriousViolations, stubApi } from "@/test/render";

describe("Rules", () => {
  it("lists active rule versions with thresholds, windows and debounce", async () => {
    stubApi();
    renderApp("/rules");

    const latency = (await screen.findByRole("rowheader", { name: "R-LAT-001 v1" })).closest("tr");
    expect(latency).toHaveTextContent("p95 over 60");
    expect(latency).toHaveTextContent("> 250");
    expect(latency).toHaveTextContent("3 / 3");
  });

  it("has no serious accessibility violation", async () => {
    stubApi();
    const { container } = renderApp("/rules");
    await screen.findByRole("rowheader", { name: "R-LAT-001 v1" });

    expect(await seriousViolations(container)).toEqual([]);
  });
});
