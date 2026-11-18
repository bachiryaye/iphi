import { graphLayout } from "./graphLayout";
import {
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useMemo } from "react";
import { Link } from "react-router";

import type { Topology, TopologyNode } from "@/shared/api/types";
import { useSearchFilter } from "@/shared/hooks/useSearchFilter";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { Timestamp } from "@/shared/status/Timestamp";

import { isImpactEdge } from "./layout";
import "@xyflow/react/dist/style.css";
import "./topology.css";

type ComponentNode = Node<{ component: TopologyNode }, "component">;

function ComponentCard({ data }: NodeProps<ComponentNode>) {
  const node = data.component;
  return (
    <div
      className={`flex h-full flex-col justify-between rounded-card border border-border bg-surface p-3 ${node.health.state === "critical" ? "shadow-[inset_3px_0_0_var(--status-critical)]" : ""}`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="truncate font-medium">{node.key}</span>
      <span className="text-small text-text-muted">
        {node.type} · {node.criticality}
      </span>
      <span className="flex items-center justify-between gap-2">
        <HealthBadge health={node.health} />
        {node.impacted_by.length > 0 && (
          <span className="text-small text-text-muted">impacted</span>
        )}
      </span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const NODE_TYPES = { component: ComponentCard };

export function TopologyGraph({ topology }: { topology: Topology }) {
  const [selected, select] = useSearchFilter(
    "component",
    topology.nodes.map((n) => n.id),
  );
  const positions = useMemo(() => graphLayout(topology), [topology]);
  const byId = new Map(topology.nodes.map((n) => [n.id, n]));
  const nodes: ComponentNode[] = topology.nodes.map((node) => ({
    id: node.id,
    type: "component",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: { component: node },
    selected: selected === node.id,
    width: 184,
    height: 96,
    ariaLabel: `${node.key}, ${node.type}, ${node.criticality}, ${node.health.state}`,
  }));
  const edges = topology.edges.map((edge) => {
    const impact = isImpactEdge(edge, byId);
    return {
      id: `${edge.dependency_id}-${edge.dependent_id}`,
      source: edge.dependency_id,
      target: edge.dependent_id,
      type: "smoothstep",
      className: impact ? "impact-edge" : "",
      style: { strokeDasharray: edge.kind === "runtime" ? "5 4" : undefined },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: impact ? "var(--status-critical)" : "var(--border-strong)",
      },
      ariaLabel: `${byId.get(edge.dependency_id)?.key ?? "?"} to ${byId.get(edge.dependent_id)?.key ?? "?"}, ${edge.kind}${impact ? ", impact" : ""}`,
    };
  });
  const detail = byId.get(selected);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_260px] border-b border-border max-lg:grid-cols-1">
      <div
        className="iphi-topology h-[360px] min-w-0"
        aria-label="Interactive component dependencies"
      >
        <ReactFlow<ComponentNode>
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          minZoom={0.2}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          edgesFocusable={true}
          deleteKeyCode={null}
          selectionKeyCode={null}
          multiSelectionKeyCode={null}
          onNodeClick={(_, node) => {
            select(node.id);
          }}
          onNodesChange={(changes) => {
            for (const change of changes) {
              if (change.type === "select" && change.selected && change.id !== selected) {
                select(change.id);
                break;
              }
            }
          }}
          onPaneClick={() => {
            select("");
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") select("");
          }}
          ariaLabelConfig={{
            "node.a11yDescription.default":
              "Press Enter or Space to select a component. Escape clears selection.",
          }}
        >
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <aside
        aria-label="Selected component"
        className="flex flex-col gap-2 border-l border-border p-4 max-lg:border-t max-lg:border-l-0"
      >
        {detail === undefined ? (
          <p className="text-text-muted">
            Select a component to inspect its state. Use the controls to zoom or fit the chain.
          </p>
        ) : (
          <>
            <h2 className="data font-semibold">{detail.key}</h2>
            <HealthBadge health={detail.health} />
            <p className="text-small text-text-muted">
              {detail.type} · {detail.criticality} criticality
            </p>
            {detail.health.evaluated_at !== null && (
              <p className="text-small text-text-muted">
                Evaluated <Timestamp iso={detail.health.evaluated_at} />
              </p>
            )}
            <p className="text-small">
              Depends on:{" "}
              {topology.edges
                .filter((e) => e.dependent_id === detail.id)
                .map((e) => byId.get(e.dependency_id)?.key ?? "?")
                .join(", ") || "none"}
            </p>
            <p className="text-small">
              Impacted by:{" "}
              {detail.impacted_by.map((id) => byId.get(id)?.key ?? "?").join(", ") || "none"}
            </p>
            <Link to={`/components/${detail.id}`} className="text-link">
              Investigate {detail.key}
            </Link>
          </>
        )}
      </aside>
    </div>
  );
}
