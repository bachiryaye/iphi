import type { RuleStatus } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { Timestamp } from "@/shared/status/Timestamp";

import { ruleCondition } from "@/features/rules/ruleText";
import { humanize } from "@/shared/format/labels";

function Observed({ status }: { status: RuleStatus }) {
  if (status.rule.metric_name === null) {
    return <>{status.sample_count > 0 ? `${String(status.sample_count)} observations` : "none"}</>;
  }
  if (status.observed_value === null)
    return <span className="text-status-unknown">no samples</span>;
  return <>{formatValue(status.observed_value, status.rule.unit)}</>;
}

function Debounce({ status }: { status: RuleStatus }) {
  const d = status.debounce;
  if (d === null) return <span className="text-text-muted">—</span>;
  return (
    <span title={`${String(d.streak)} of ${String(d.required)} consecutive evaluations`}>
      {d.pending_state} {d.streak}/{d.required}
    </span>
  );
}

/** One row per applicable rule with its justification (§6.3); Unknown is never Healthy. */
export function RulesTable({ rules }: { rules: readonly RuleStatus[] }) {
  if (rules.length === 0) {
    return (
      <p className="px-4 py-3 text-text-muted">
        No rule evaluated yet: the worker evaluates every rule once its first sample slot is
        collected.
      </p>
    );
  }
  return (
    <>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">State</th>
              <th scope="col">Rule</th>
              <th scope="col">Condition</th>
              <th scope="col" className="num">
                Observed
              </th>
              <th scope="col">Debounce</th>
              <th scope="col">Since, evaluation</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((status) => (
              <tr
                key={status.rule.key}
                className={status.health.state === "critical" ? "row-critical" : undefined}
              >
                <td>
                  <HealthBadge health={status.health} />
                </td>
                <th scope="row" className="whitespace-nowrap">
                  <span className="data">
                    {status.rule.key} v{status.rule.version}
                  </span>
                  <span className="block text-small text-text-muted">
                    {humanize(status.rule.failure_class)}
                  </span>
                </th>
                <td className="min-w-56 py-2">
                  <span className="data block">{ruleCondition(status.rule)}</span>
                  <span className="block text-small text-text-muted">{status.explanation}</span>
                </td>
                <td className="num data whitespace-nowrap">
                  <Observed status={status} />
                </td>
                <td className="data whitespace-nowrap">
                  <Debounce status={status} />
                </td>
                <td className="whitespace-nowrap">
                  {status.health.since === null ? "—" : <Timestamp iso={status.health.since} />}
                  <span
                    className="data block text-small text-text-muted"
                    title="Stored evaluation that set the state"
                  >
                    #{status.state_evaluation_id}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
        Unknown means the rule had no evidence in its window. It is never counted as Healthy.
      </p>
    </>
  );
}
