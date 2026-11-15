import { describe, expect, it } from "vitest";

import { formatAge, formatDuration, formatSeconds, formatUtcDateTime, formatUtcTime } from "./time";

const instant = new Date("2026-11-12T10:42:07Z");

describe("time formatting", () => {
  it("formats UTC times on a 24-hour clock", () => {
    expect(formatUtcTime(instant)).toBe("10:42:07");
    expect(formatUtcTime(new Date("2026-11-12T00:05:09Z"))).toBe("00:05:09");
  });

  it("formats absolute UTC timestamps as the design system writes them", () => {
    expect(formatUtcDateTime(instant)).toBe("2026-11-12 10:42:07 UTC");
  });

  it("keeps the unit attached to durations", () => {
    expect(formatSeconds(5)).toBe("5\u00a0s");
    expect(formatSeconds(0.5)).toBe("0.5\u00a0s");
  });
});

describe("durations", () => {
  it("keeps two units at most and never drops the unit", () => {
    expect(formatDuration(42)).toBe("42\u00a0s");
    expect(formatDuration(135)).toBe("2\u00a0min 15\u00a0s");
    expect(formatDuration(14 * 60 + 5)).toBe("14\u00a0min");
    expect(formatDuration(3 * 3600 + 5 * 60)).toBe("3\u00a0h 05\u00a0min");
    expect(formatDuration(-3)).toBe("0\u00a0s");
  });

  it("states ages relative to a given instant", () => {
    expect(formatAge(new Date("2026-11-12T10:40:07Z"), instant)).toBe("2\u00a0min ago");
  });
});
