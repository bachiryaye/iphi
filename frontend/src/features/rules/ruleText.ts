import type { HealthRule } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";

export const OPERATOR = { gt: ">", ge: "≥", lt: "<" } as const;

/** `p95 over 60 s`: what a threshold is compared with. */
export function measureBasis(rule: HealthRule): string {
  const window = `${String(rule.window_seconds)}\u00a0s`;
  switch (rule.aggregation) {
    case "last":
      return `latest value in ${window}`;
    case "avg":
      return `average over ${window}`;
    case "ratio":
      return `share over ${window}`;
    case null:
      return `any observation in ${window}`;
    default:
      return `${rule.aggregation} over ${window}`;
  }
}

/** `p95(probe_latency_ms, 60 s) > 250 ms | > 1000 ms` as the rule evaluates it. */
export function ruleCondition(rule: HealthRule): string {
  if (rule.metric_name === null || rule.aggregation === null || rule.operator === null) {
    return `any observation in ${String(rule.window_seconds)}\u00a0s`;
  }
  const op = OPERATOR[rule.operator];
  const expr = `${rule.aggregation}(${rule.metric_name}, ${String(rule.window_seconds)}\u00a0s)`;
  const levels = [
    rule.warning && `warning ${op} ${formatValue(rule.warning.threshold, rule.unit)}`,
    rule.critical && `critical ${op} ${formatValue(rule.critical.threshold, rule.unit)}`,
  ].filter(Boolean);
  return `${expr}: ${levels.join(", ")}`;
}
