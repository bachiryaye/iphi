import type { IncidentEvidence } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";

/** One line on what a piece of evidence says, as stored. */
export function evidenceSummary(item: IncidentEvidence): string {
  if (item.sample !== null) {
    return `${item.sample.metric_name} = ${formatValue(item.sample.value, item.sample.unit)}`;
  }
  if (item.log !== null) return `${item.log.severity.toUpperCase()} ${item.log.message}`;
  if (item.evaluation !== null) {
    const e = item.evaluation;
    return `${e.rule.key} v${String(e.rule.version)} evaluated ${e.state}: ${e.explanation}`;
  }
  return item.kind;
}

export function evidenceTime(item: IncidentEvidence): string {
  return (
    item.sample?.observed_at ??
    item.log?.observed_at ??
    item.evaluation?.evaluated_at ??
    item.added_at
  );
}
