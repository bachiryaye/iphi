import type { KeyMetric } from "@/shared/api/types";

interface Zone {
  from: number;
  to: number;
  start: number;
  end: number;
}

/**
 * HPHMI zone scale (§6.1): normal range on 60 % of the track, warning band 20 %, critical
 * band 20 %, linear inside each zone. A missing level hands its share to its neighbour.
 */
export function zones(metric: KeyMetric): Zone[] {
  const { display_min: min, display_max: max } = metric;
  const warning = metric.warning_threshold;
  const critical = metric.critical_threshold;
  if (warning !== null && critical !== null) {
    return [
      { from: min, to: warning, start: 0, end: 60 },
      { from: warning, to: critical, start: 60, end: 80 },
      { from: critical, to: max, start: 80, end: 100 },
    ];
  }
  const only = warning ?? critical ?? max;
  const split = warning !== null ? 60 : 80;
  return [
    { from: min, to: only, start: 0, end: split },
    { from: only, to: max, start: split, end: 100 },
  ];
}

/** Track position in percent; clamped, with `beyond` telling the value is off scale. */
export function meterPosition(metric: KeyMetric, value: number): { pct: number; beyond: boolean } {
  const all = zones(metric);
  const first = all[0];
  const last = all[all.length - 1];
  if (first === undefined || last === undefined) return { pct: 0, beyond: false };
  if (value <= first.from) return { pct: 0, beyond: value < first.from };
  if (value >= last.to) return { pct: 100, beyond: value > last.to };
  const zone = all.find((z) => value <= z.to) ?? last;
  const span = zone.to - zone.from;
  const ratio = span <= 0 ? 0 : (value - zone.from) / span;
  return { pct: zone.start + ratio * (zone.end - zone.start), beyond: false };
}
