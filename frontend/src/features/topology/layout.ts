import type { TopologyEdge, TopologyNode } from "@/shared/api/types";

/** An edge lies on an impact path when the dependent is impacted through this dependency. */
export function isImpactEdge(edge: TopologyEdge, nodes: Map<string, TopologyNode>): boolean {
  const dependent = nodes.get(edge.dependent_id);
  const dependency = nodes.get(edge.dependency_id);
  if (dependent === undefined || dependency === undefined) return false;
  if (dependent.impacted_by.includes(edge.dependency_id)) return true;
  return dependency.impacted_by.some((id) => dependent.impacted_by.includes(id));
}
