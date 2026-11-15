import { Link } from "react-router";

import type { Component } from "@/shared/api/types";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { ImpactNote } from "@/shared/status/ImpactNote";
import { KeyMetricCell } from "@/shared/status/KeyMetricCell";
import { Timestamp } from "@/shared/status/Timestamp";

/** One row per component, in the order the API lists them; every row leads to the Component view. */
export function ComponentsTable({ components }: { components: readonly Component[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col">State</th>
            <th scope="col" className="max-lg:hidden">
              Criticality
            </th>
            <th scope="col">Key metric</th>
            <th scope="col" className="max-lg:hidden">
              Impact
            </th>
            <th scope="col" className="num">
              Last evaluation
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
                <span className="block text-small text-text-muted">{component.type}</span>
              </th>
              <td>
                <HealthBadge health={component.health} />
              </td>
              <td className="text-text-muted max-lg:hidden">{component.criticality}</td>
              <td>
                <KeyMetricCell metric={component.key_metric} />
              </td>
              <td className="max-lg:hidden">
                <ImpactNote by={component.impacted_by} />
              </td>
              <td className="num whitespace-nowrap text-text-muted">
                {component.health.evaluated_at === null ? (
                  "never"
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
