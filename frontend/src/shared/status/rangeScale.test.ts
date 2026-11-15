import { describe, expect, it } from "vitest";

import { latencyMetric } from "@/test/apiFixtures";

import { meterPosition, zones } from "./rangeScale";

const latency = latencyMetric(42);

describe("range meter zone scale", () => {
  it("gives the normal range 60 % of the track, each band 20 %", () => {
    expect(zones(latency).map((z) => [z.from, z.to, z.start, z.end])).toEqual([
      [0, 250, 0, 60],
      [250, 1000, 60, 80],
      [1000, 1250, 80, 100],
    ]);
  });

  it("is linear inside each zone", () => {
    expect(meterPosition(latency, 125).pct).toBeCloseTo(30);
    expect(meterPosition(latency, 625).pct).toBeCloseTo(70);
    expect(meterPosition(latency, 1125).pct).toBeCloseTo(90);
  });

  it("pins off-scale values to the end and says so", () => {
    expect(meterPosition(latency, 5000)).toEqual({ pct: 100, beyond: true });
    expect(meterPosition(latency, 1250)).toEqual({ pct: 100, beyond: false });
    expect(meterPosition(latency, 0)).toEqual({ pct: 0, beyond: false });
  });

  it("hands a missing level's share to its neighbour", () => {
    const criticalOnly = { ...latency, warning_threshold: null };
    expect(zones(criticalOnly).map((z) => [z.start, z.end])).toEqual([
      [0, 80],
      [80, 100],
    ]);
  });
});
