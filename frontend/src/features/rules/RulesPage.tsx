import { useT } from "@/shared/i18n/context";
import { useHealthRules } from "@/shared/api/queries";
import { humanize } from "@/shared/format/labels";
import { formatValue } from "@/shared/format/number";
import { Card } from "@/shared/ui/Card";
import { LoadError, SkeletonRows } from "@/shared/ui/QueryStates";

import { measureBasis, OPERATOR } from "./ruleText";

/** Read-only catalog of the active rule versions (§6.6). */
export function RulesPage() {
  const t = useT();
  const rules = useHealthRules();
  return (
    <>
      <h1 className="text-display font-semibold">{t("Rules")}</h1>
      <Card
        title={t("Health rules")}
        titleId="health-rules-title"
        busy={rules.isPending}
        meta={<span>{t("active versions, read-only; a change creates a new version")}</span>}
      >
        {rules.isPending && <SkeletonRows rows={6} />}
        {rules.isError && rules.data === undefined && (
          <LoadError what={t("health rules")} query={rules} />
        )}
        {rules.data !== undefined && (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">{t("Rule")}</th>
                  <th scope="col">{t("Class")}</th>
                  <th scope="col">{t("Measure")}</th>
                  <th scope="col">{t("Warning (clear)")}</th>
                  <th scope="col">{t("Critical (clear)")}</th>
                  <th scope="col">{t("Raise / clear")}</th>
                  <th scope="col">{t("Applies to")}</th>
                  <th scope="col">{t("Rationale and recommendation")}</th>
                </tr>
              </thead>
              <tbody>
                {rules.data.items.map((rule) => {
                  const op = rule.operator === null ? "" : OPERATOR[rule.operator];
                  const level = (l: typeof rule.warning) =>
                    l === null
                      ? "—"
                      : `${op} ${formatValue(l.threshold, rule.unit, t)} (${formatValue(l.clear, rule.unit, t)})`;
                  const targets = [...rule.target_types, ...rule.target_components];
                  return (
                    <tr key={rule.id}>
                      <th scope="row" className="data whitespace-nowrap">
                        {rule.key} v{rule.version}
                      </th>
                      <td>{humanize(rule.failure_class, t)}</td>
                      <td className="py-2">
                        <span className="data block">
                          {rule.metric_name ?? t("any observation")}
                        </span>
                        <span className="block text-small text-text-muted">
                          {measureBasis(rule, t)}
                        </span>
                      </td>
                      <td className="data whitespace-nowrap">{level(rule.warning)}</td>
                      <td className="data whitespace-nowrap">{level(rule.critical)}</td>
                      <td className="data whitespace-nowrap">
                        {rule.raise_after} / {rule.clear_after}
                      </td>
                      <td className="text-text-muted">
                        {targets.length === 0 ? t("all components") : targets.join(", ")}
                      </td>
                      <td className="max-w-[48ch] py-2">
                        <span className="block">{rule.rationale}</span>
                        <span className="block text-small text-text-muted">
                          {rule.recommendation}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
          {t(
            "Raise / clear: consecutive evaluations, one per 5 s sample slot, needed to enter a worse state or return to a better one. Thresholds are demonstration values for the simulated platform.",
          )}
        </p>
      </Card>
    </>
  );
}
