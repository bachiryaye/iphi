import { useT } from "@/shared/i18n/context";
import { Link } from "react-router";

import type { Component } from "@/shared/api/types";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { ImpactNote } from "@/shared/status/ImpactNote";
import { KeyMetricCell } from "@/shared/status/KeyMetricCell";
import { Timestamp } from "@/shared/status/Timestamp";

/** One row per component, in the order the API lists them; every row leads to the Component view. */
export function ComponentsTable({ components }: { components: readonly Component[] }) {
  const t = useT();
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">{t("Component")}</th>
            <th scope="col">{t("State")}</th>
            <th scope="col" className="max-lg:hidden">
              {t("Criticality")}
            </th>
            <th scope="col">{t("Key metric")}</th>
            <th scope="col" className="max-lg:hidden">
              {t("Impact")}
            </th>
            <th scope="col" className="num">
              {t("Last evaluation")}
            </th>
          </tr>
        </thead>
        <tbody>
          {components.map((component) => (
            <tr
              key={component.id}
              className={component.health.state === "critical" ? "row-critical" : undefined}
            >
              <th scope="row">
                <Link
                  to={`/components/${component.id}`}
                  className="block font-medium whitespace-nowrap text-text hover:underline"
                >
                  {component.key}
                </Link>
                <span className="block text-small text-text-muted">{t.label(component.type)}</span>
              </th>
              <td>
                <HealthBadge health={component.health} />
              </td>
              <td className="text-text-muted max-lg:hidden">{t.label(component.criticality)}</td>
              <td>
                <KeyMetricCell metric={component.key_metric} />
              </td>
              <td className="max-lg:hidden">
                <ImpactNote by={component.impacted_by} />
              </td>
              <td className="num whitespace-nowrap text-text-muted">
                {component.health.evaluated_at === null ? (
                  t("never")
                ) : (
                  <Timestamp iso={component.health.evaluated_at} format="age" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
