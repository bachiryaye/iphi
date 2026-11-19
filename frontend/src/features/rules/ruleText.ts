import { english, type Translator } from "@/shared/i18n/translate";

import type { HealthRule } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";

export const OPERATOR = { gt: ">", ge: "≥", lt: "<" } as const;

/** `p95 over 60 s`: what a threshold is compared with. */
export function measureBasis(rule: HealthRule, t: Translator = english): string {
  const window = `${String(rule.window_seconds)}\u00a0s`;
  switch (rule.aggregation) {
    case "last":
      return t("latest value in {window}", { window });
    case "avg":
      return t("average over {window}", { window });
    case "ratio":
      return t("share over {window}", { window });
    case null:
      return t("any observation in {window}", { window });
    default:
      return t("{aggregation} over {window}", { aggregation: rule.aggregation, window });
  }
}

/** `p95(probe_latency_ms, 60 s) > 250 ms | > 1000 ms` as the rule evaluates it. */
export function ruleCondition(rule: HealthRule, t: Translator = english): string {
  if (rule.metric_name === null || rule.aggregation === null || rule.operator === null) {
    return t("any observation in {window}", { window: `${String(rule.window_seconds)}\u00a0s` });
  }
  const op = OPERATOR[rule.operator];
  const expr = `${rule.aggregation}(${rule.metric_name}, ${String(rule.window_seconds)}\u00a0s)`;
  const levels = [
    rule.warning &&
      `${t("Warning").toLowerCase()} ${op} ${formatValue(rule.warning.threshold, rule.unit, t)}`,
    rule.critical &&
      `${t("Critical").toLowerCase()} ${op} ${formatValue(rule.critical.threshold, rule.unit, t)}`,
  ].filter(Boolean);
  return `${expr}: ${levels.join(", ")}`;
}
