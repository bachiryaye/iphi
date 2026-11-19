import { describe, expect, it } from "vitest";

import { french } from "./messages";
import { translator } from "./translate";
import { formatNumber, formatValue } from "@/shared/format/number";
import { formatAge } from "@/shared/format/time";

const en = translator("en"),
  fr = translator("fr");

describe("presentation translation boundaries", () => {
  it("translates health labels without changing canonical or untrusted evidence", () => {
    expect(fr("Unknown")).toBe("Inconnu");
    expect(en("Unknown")).toBe("Unknown");
    expect(fr.label("R-AVAIL-001")).toBe("R-AVAIL-001");
    expect(fr.label("collector-01 unreachable <script>alert(1)</script>")).toBe(
      "collector-01 unreachable <script>alert(1)</script>",
    );
  });
  it("preserves prototype property names as unknown technical labels", () => {
    for (const label of ["constructor", "__proto__", "toString", "hasOwnProperty"])
      expect(fr.label(label)).toBe(label);
  });
  it("reorders named values and formats relative age and numbers by locale", () => {
    expect(fr("{duration} ago", { duration: "4 min" })).toBe("il y a 4 min");
    expect(formatAge(new Date("2026-11-19T12:00:00Z"), new Date("2026-11-19T12:04:00Z"), fr)).toBe(
      "il y a 4\u00a0min",
    );
    expect(formatNumber(42.5, fr)).toBe("42,5");
    expect(formatValue(42.5, "ms", fr)).toBe("42,5\u00a0ms");
    expect(formatValue(42.5, "ms", en)).toBe("42.5\u00a0ms");
  });
  it("preserves every interpolation value in the French catalog", () => {
    const placeholders = (value: string) =>
      [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
    for (const [key, value] of Object.entries(french)) {
      expect(value.trim(), key).not.toBe("");
      expect(placeholders(value), key).toEqual(placeholders(key));
    }
  });
});
