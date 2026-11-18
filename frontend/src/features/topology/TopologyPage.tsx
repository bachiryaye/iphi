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
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border px-4 py-2.5 text-small text-text-muted">
      <li className="inline-flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="28" y2="4" strokeWidth="1.5" className="stroke-border-strong" />
        </svg>
        data flow
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
        </svg>
        runtime dependency
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
        </svg>
        impact path from a Critical or Unknown component
      </li>
      <li>Arrows follow the data, from a dependency to its dependent.</li>
    </ul>
  );
}

function DependencyTable({ topology }: { topology: Topology }) {
  const keys = new Map(topology.nodes.map((n) => [n.id, n.key]));
  return (
    <div className="overflow-x-auto border-t border-border">
      <table className="data-table">
        <caption className="sr-only">Components and their dependencies</caption>
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col">State</th>
            <th scope="col">Depends on</th>
            <th scope="col">Impacted by</th>
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
                  .map((e) => `${keys.get(e.dependency_id) ?? "?"} (${humanize(e.kind)})`)
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
  const platforms = usePlatforms();
  const platformId = platforms.data?.items[0]?.id;
  const topology = useTopology(platformId);
  const error = platforms.error ?? topology.error;
  return (
    <>
      <h1 className="text-display font-semibold">Topology</h1>
      <Card
        title="Dependency chain"
        titleId="topology-title"
        busy={topology.isPending}
        meta={
          <>
            <span>pan, zoom and select · arrows follow the data</span>
            <SimTag />
            <RefreshMeta updatedAt={topology.dataUpdatedAt} failed={topology.isError} />
          </>
        }
      >
        {topology.data === undefined && error === null && <SkeletonRows rows={4} />}
        {topology.data === undefined && error !== null && (
          <LoadError what="the topology" query={platformId === undefined ? platforms : topology} />
        )}
        {platforms.data !== undefined && platformId === undefined && (
          <EmptyState title="No platform configured.">
            The bootstrap seeds the simulated platform.
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
