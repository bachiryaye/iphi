import { useT } from "@/shared/i18n/context";
import { lazy, Suspense } from "react";
import { Link } from "react-router";

import { usePlatforms, useTopology } from "@/shared/api/queries";
import type { Topology } from "@/shared/api/types";
import { humanize } from "@/shared/format/labels";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { SimTag } from "@/shared/status/SimTag";
import { Card } from "@/shared/ui/Card";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

const TopologyGraph = lazy(() =>
  import("./TopologyGraph").then((m) => ({ default: m.TopologyGraph })),
);

function Legend() {
  const t = useT();
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border px-4 py-2.5 text-small text-text-muted">
      <li className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="28" y2="4" strokeWidth="1.5" className="stroke-border-strong" />
        </svg>{" "}
        {t("data flow")}
      </li>
      <li className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line
            x1="0"
            y1="4"
            x2="28"
            y2="4"
            strokeWidth="1.5"
            strokeDasharray="5 4"
            className="stroke-border-strong"
          />
        </svg>{" "}
        {t("runtime dependency")}
      </li>
      <li className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line
            x1="0"
            y1="4"
            x2="28"
            y2="4"
            strokeWidth="2"
            className="stroke-status-critical opacity-60"
          />
        </svg>{" "}
        {t("impact path from a Critical or Unknown component")}
      </li>
      <li>{t("Arrows follow the data, from a dependency to its dependent.")}</li>
    </ul>
  );
}

function DependencyTable({ topology }: { topology: Topology }) {
  const t = useT();
  const keys = new Map(topology.nodes.map((n) => [n.id, n.key]));
  return (
    <div className="overflow-x-auto border-t border-border">
      <table className="data-table">
        <caption className="sr-only">{t("Components and their dependencies")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("Component")}</th>
            <th scope="col">{t("State")}</th>
            <th scope="col">{t("Depends on")}</th>
            <th scope="col">{t("Impacted by")}</th>
          </tr>
        </thead>
        <tbody>
          {topology.nodes.map((node) => (
            <tr key={node.id}>
              <th scope="row">
                <Link
                  to={`/components/${node.id}`}
                  className="font-medium text-text hover:underline"
                >
                  {node.key}
                </Link>
              </th>
              <td>
                <HealthBadge health={node.health} />
              </td>
              <td className="text-text-muted">
                {topology.edges
                  .filter((e) => e.dependent_id === node.id)
                  .map((e) => `${keys.get(e.dependency_id) ?? "?"} (${humanize(e.kind, t)})`)
                  .join(", ") || "none"}
              </td>
              <td className="text-text-muted">
                {node.impacted_by.map((id) => keys.get(id) ?? "?").join(", ") || "none"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TopologyPage() {
  const t = useT();
  const platforms = usePlatforms();
  const platformId = platforms.data?.items[0]?.id;
  const topology = useTopology(platformId);
  const error = platforms.error ?? topology.error;
  return (
    <>
      <h1 className="text-display font-semibold">{t("Topology")}</h1>
      <Card
        title={t("Dependency chain")}
        titleId="topology-title"
        busy={topology.isPending}
        meta={
          <>
            <span>{t("pan, zoom and select · arrows follow the data")}</span>
            <SimTag />
            <RefreshMeta updatedAt={topology.dataUpdatedAt} failed={topology.isError} />
          </>
        }
      >
        {topology.data === undefined && error === null && <SkeletonRows rows={4} />}
        {topology.data === undefined && error !== null && (
          <LoadError
            what={t("the topology")}
            query={platformId === undefined ? platforms : topology}
          />
        )}
        {platforms.data !== undefined && platformId === undefined && (
          <EmptyState title={t("No platform configured.")}>
            {t("The bootstrap seeds the simulated platform.")}
          </EmptyState>
        )}
        {topology.data !== undefined && (
          <div className={staleClass(topology.isError)}>
            <Suspense fallback={<SkeletonRows rows={4} />}>
              <TopologyGraph topology={topology.data} />
            </Suspense>
            <Legend />
            <DependencyTable topology={topology.data} />
          </div>
        )}
      </Card>
    </>
  );
}
