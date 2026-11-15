import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { components, latencyMetric } from "@/test/apiFixtures";

import { KeyMetricCell } from "./KeyMetricCell";

const renderCell = (metric: Parameters<typeof KeyMetricCell>[0]["metric"]) =>
  render(
    <MemoryRouter>
      <KeyMetricCell metric={metric} />
    </MemoryRouter>,
  );

describe("KeyMetricCell", () => {
  it("draws a meter whose text alternative states value, normal range and state", () => {
    renderCell(latencyMetric(42));

    const meter = screen.getByRole("meter", { name: "probe latency" });
    expect(meter).toHaveAttribute("aria-valuenow", "42");
    expect(meter).toHaveAttribute("aria-valuetext", "42 ms, normal below 250 ms, Healthy");
    expect(meter).toHaveTextContent("42ms");
  });

  it("shows the rule details on keyboard focus", async () => {
    renderCell(latencyMetric(42));

    await userEvent.tab();

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent(/p95\(probe_latency_ms, 60\ss\)/);
    expect(tooltip).toHaveTextContent("R-LAT-001 v1");
  });

  it("says no data instead of drawing a pointer when the window is empty", () => {
    renderCell(latencyMetric(null));

    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "probe latency: no samples in the last 60 s, Unknown",
    );
    expect(screen.getByText("no data")).toBeInTheDocument();
  });

  it("writes a failed probe as text, never as a gauge", () => {
    renderCell(components.find((c) => c.key === "collector-01")?.key_metric ?? null);

    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText(/DOWN/)).toHaveTextContent("DOWN since 10:39:47 UTC(R-AVAIL-001)");
  });

  it("draws no pointer for a stale value, which is no current evidence", () => {
    renderCell({ ...latencyMetric(42), state: "unknown" });

    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "probe latency: no current value, Unknown",
    );
  });

  it("never reports a stale probe result as DOWN or up", () => {
    const down = components.find((c) => c.key === "collector-01")?.key_metric ?? null;
    renderCell(down === null ? null : { ...down, state: "unknown" });

    expect(screen.queryByText(/DOWN/)).not.toBeInTheDocument();
    expect(screen.getByText("no current probe result")).toBeInTheDocument();
  });

  it("does not claim an outage before the debounce confirms it", () => {
    const down = components.find((c) => c.key === "collector-01")?.key_metric ?? null;
    renderCell(down === null ? null : { ...down, state: "healthy" });

    expect(screen.queryByText(/DOWN/)).not.toBeInTheDocument();
    expect(screen.getByText(/Probe failed, not yet confirmed/)).toBeInTheDocument();
  });

  it("states that a component was never evaluated", () => {
    renderCell(null);

    expect(screen.getByText("Not evaluated yet")).toBeInTheDocument();
  });
});
