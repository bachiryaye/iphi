import { Link } from "react-router";

import { usePlatforms, useTopology } from "@/shared/api/queries";
import type { Topology } from "@/shared/api/types";
import { humanize } from "@/shared/format/labels";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { SimTag } from "@/shared/status/SimTag";
import { Card } from "@/shared/ui/Card";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { isImpactEdge, layoutTopology, type Placed } from "./layout";

const NODE_W = 156;
const NODE_H = 80;
const COL_W = 192;
const ROW_H = 120;
const PAD = 12;

function position(p: Placed) {
  return { x: PAD + p.column * COL_W, y: PAD + p.row * ROW_H };
}

function edgePath(from: Placed, to: Placed): string {
  const a = position(from);
  const b = position(to);
  if (from.column === to.column) {
    const x = a.x + NODE_W / 2;
    const [top, bottom] = a.y < b.y ? [a.y + NODE_H, b.y] : [b.y + NODE_H, a.y];
    return `M${String(x)} ${String(bottom)} V${String(top)}`;
  }
  const x1 = a.x + NODE_W;
  const y1 = a.y + NODE_H / 2;
  const x2 = b.x;
  const y2 = b.y + NODE_H / 2;
  const mid = (x1 + x2) / 2;
  return `M${String(x1)} ${String(y1)} C${String(mid)} ${String(y1)} ${String(mid)} ${String(y2)} ${String(x2)} ${String(y2)}`;
}

function Graph({ topology }: { topology: Topology }) {
  const placed = layoutTopology(topology.nodes, topology.edges);
  const byId = new Map(placed.map((p) => [p.node.id, p]));
  const nodes = new Map(topology.nodes.map((n) => [n.id, n]));
  const columns = Math.max(0, ...placed.map((p) => p.column)) + 1;
  const rows = Math.max(0, ...placed.map((p) => p.row)) + 1;
  const width = PAD * 2 + (columns - 1) * COL_W + NODE_W;
  const height = PAD * 2 + (rows - 1) * ROW_H + NODE_H;

  return (
    <div className="overflow-x-auto px-2 py-2">
      <div className="relative" style={{ width, height }}>
        <svg width={width} height={height} className="absolute inset-0" aria-hidden="true">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="8"
              markerHeight="8"
              orient="auto"
            >
              <path d="M0 0 8 4 0 8z" className="fill-border-strong" />
            </marker>
            <marker
              id="arrow-impact"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="8"
              markerHeight="8"
              orient="auto"
            >
              <path d="M0 0 8 4 0 8z" className="fill-status-critical" />
            </marker>
          </defs>
          {topology.edges.map((edge) => {
            const from = byId.get(edge.dependency_id);
            const to = byId.get(edge.dependent_id);
            if (from === undefined || to === undefined) return null;
            const impact = isImpactEdge(edge, nodes);
            return (
              <path
                key={`${edge.dependency_id}-${edge.dependent_id}`}
                d={edgePath(from, to)}
                fill="none"
                strokeWidth={impact ? 2 : 1.5}
                strokeDasharray={edge.kind === "runtime" ? "5 4" : undefined}
                markerEnd={`url(#${impact ? "arrow-impact" : "arrow"})`}
                className={impact ? "stroke-status-critical opacity-60" : "stroke-border-strong"}
              />
            );
          })}
        </svg>
        {placed.map((p) => {
          const { x, y } = position(p);
          const critical = p.node.health.state === "critical";
          return (
            <div
              key={p.node.id}
              className={`absolute flex flex-col justify-between rounded-card border border-border bg-surface px-3 py-2 ${
                critical ? "shadow-[inset_3px_0_0_var(--status-critical)]" : ""
              }`}
              style={{ left: x, top: y, width: NODE_W, height: NODE_H }}
            >
              <Link
                to={`/components/${p.node.id}`}
                className="truncate font-medium text-text hover:underline"
              >
                {p.node.key}
              </Link>
              <span className="truncate text-small text-text-muted">
                {p.node.type}, {p.node.criticality}
              </span>
              <span className="flex items-center justify-between gap-2">
                <HealthBadge health={p.node.health} />
                {p.node.impacted_by.length > 0 && (
                  <span className="text-small text-text-muted">impacted</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

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
            <span>fixed layout, left to right in the direction of the data</span>
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
            <Graph topology={topology.data} />
            <Legend />
            <DependencyTable topology={topology.data} />
          </div>
        )}
      </Card>
    </>
  );
}
