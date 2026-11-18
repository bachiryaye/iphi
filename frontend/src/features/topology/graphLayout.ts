import dagre from "@dagrejs/dagre";
import type { Topology } from "@/shared/api/types";

export function graphLayout(topology: Topology) {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 54, marginx: 12, marginy: 12 });
  for (const node of topology.nodes) graph.setNode(node.id, { width: 184, height: 96 });
  for (const edge of topology.edges) graph.setEdge(edge.dependency_id, edge.dependent_id);
  dagre.layout(graph);
  return new Map(
    topology.nodes.map((node) => {
      const p: unknown = graph.node(node.id);
      if (
        typeof p !== "object" ||
        p === null ||
        !("x" in p) ||
        !("y" in p) ||
        typeof p.x !== "number" ||
        typeof p.y !== "number"
      ) {
        throw new Error("The topology layout did not return a component position.");
      }
      return [node.id, { x: p.x - 92, y: p.y - 48 }] as const;
    }),
  );
}
