import { describe, expect, it } from "vitest";

import { formatSeconds, formatUtcDateTime, formatUtcTime } from "./time";

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
