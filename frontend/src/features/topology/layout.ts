import type { TopologyEdge, TopologyNode } from "@/shared/api/types";

export interface Placed {
  node: TopologyNode;
  column: number;
  row: number;
}

/**
 * Fixed left-to-right layout in the direction of the data flow (§6.2): a node's column is its
 * longest data-flow path from a source; a node with only runtime edges sits under the first
 * component depending on it. Pure layout, no health logic.
 */
export function layoutTopology(
  nodes: readonly TopologyNode[],
  edges: readonly TopologyEdge[],
): Placed[] {
  const flow = edges.filter((e) => e.kind === "data_flow");
  const depth = new Map<string, number>();
  const visit = (id: string, seen: Set<string>): number => {
    const known = depth.get(id);
    if (known !== undefined) return known;
    if (seen.has(id)) return 0;
    seen.add(id);
    const upstream = flow.filter((e) => e.dependent_id === id);
    const d =
      upstream.length === 0
        ? 0
        : 1 + Math.max(...upstream.map((e) => visit(e.dependency_id, seen)));
    depth.set(id, d);
    return d;
  };
  const inFlow = new Set(flow.flatMap((e) => [e.dependent_id, e.dependency_id]));
  for (const node of nodes) if (inFlow.has(node.id)) visit(node.id, new Set());

  const column = new Map<string, number>();
  for (const node of nodes) {
    const d = depth.get(node.id);
    if (d !== undefined) {
      column.set(node.id, d);
      continue;
    }
    const dependents = edges
      .filter((e) => e.dependency_id === node.id)
      .map((e) => depth.get(e.dependent_id) ?? 0);
    column.set(node.id, dependents.length === 0 ? 0 : Math.min(...dependents));
  }

  const rows = new Map<number, number>();
  const ordered = [...nodes].sort((a, b) => Number(!inFlow.has(a.id)) - Number(!inFlow.has(b.id)));
  return ordered.map((node) => {
    const c = column.get(node.id) ?? 0;
    const row = rows.get(c) ?? 0;
    rows.set(c, row + 1);
    return { node, column: c, row };
  });
}

/** An edge lies on an impact path when the dependent is impacted through this dependency. */
export function isImpactEdge(edge: TopologyEdge, nodes: Map<string, TopologyNode>): boolean {
  const dependent = nodes.get(edge.dependent_id);
  const dependency = nodes.get(edge.dependency_id);
  if (dependent === undefined || dependency === undefined) return false;
  if (dependent.impacted_by.includes(edge.dependency_id)) return true;
  return dependency.impacted_by.some((id) => dependent.impacted_by.includes(id));
}
