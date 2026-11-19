import { english, type Translator } from "@/shared/i18n/translate";

import type { RuleStatus } from "@/shared/api/types";
import type { Threshold } from "@/shared/charts/metricChart";

import { measureBasis } from "@/features/rules/ruleText";

/** Thresholds of the rules judging this metric; the probe result has none worth drawing. */
export function thresholdsFor(
  metric: string,
  rules: readonly RuleStatus[],
  t: Translator = english,
): Threshold[] {
  if (metric === "up") return [];
  return rules
    .filter((r) => r.rule.metric_name === metric)
    .flatMap((r) => {
      const basis = `${r.rule.key}: ${measureBasis(r.rule, t)}`;
      const levels: Threshold[] = [];
      if (r.rule.warning) levels.push({ level: "warning", value: r.rule.warning.threshold, basis });
      if (r.rule.critical) {
        levels.push({ level: "critical", value: r.rule.critical.threshold, basis });
      }
      return levels;
    });
}
