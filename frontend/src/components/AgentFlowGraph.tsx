/**
 * AgentFlowGraph – ReactFlow-based real-time agent communication visualiser.
 * Nodes pulse green when running, grey when idle, bright when done.
 * Edges animate (glow) when data is handed off between agents.
 */
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  MarkerType,
  Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AgentState } from "../hooks/useAgentSocket";

// ─── Node positions ───────────────────────────────────────────────────────────
const NODE_DEFS: Array<{ id: string; label: string; emoji: string; x: number; y: number }> = [
  { id: "Orchestrator",    label: "Orchestrator",    emoji: "🎯", x: 420, y: 260 },
  { id: "SolarAnalyst",    label: "Solar Analyst",   emoji: "☀️", x: 0,   y: 0   },
  { id: "BatteryManager",  label: "Battery Manager", emoji: "🔋", x: 0,   y: 200 },
  { id: "GridArbitrage",   label: "Grid Arbitrage",  emoji: "⚡", x: 0,   y: 400 },
  { id: "FuelScout",       label: "Fuel Scout",      emoji: "⛽", x: 840, y: 0   },
  { id: "Logistics",       label: "Logistics",       emoji: "🗺️", x: 840, y: 200 },
  { id: "MT10Calculator",  label: "MT-10 Calc",      emoji: "🏍️", x: 840, y: 400 },
  { id: "MacroGeopolitics",label: "Macro & FX",      emoji: "🌐", x: 420, y: 480 },
  { id: "RideScout",       label: "Ride Scout",      emoji: "🌤️", x: 420, y: 0   },
];

// ─── Edge definitions (parent → child) ───────────────────────────────────────
const EDGE_DEFS: Array<{ source: string; target: string }> = [
  { source: "Orchestrator",   target: "SolarAnalyst"    },
  { source: "Orchestrator",   target: "FuelScout"       },
  { source: "Orchestrator",   target: "MacroGeopolitics"},
  { source: "Orchestrator",   target: "RideScout"       },
  { source: "SolarAnalyst",   target: "BatteryManager"  },
  { source: "BatteryManager", target: "GridArbitrage"   },
  { source: "FuelScout",      target: "Logistics"       },
  { source: "Logistics",      target: "MT10Calculator"  },
];

function nodeStyle(status: string | undefined) {
  switch (status) {
    case "running":
      return {
        background: "#166534",
        border: "2px solid #22c55e",
        boxShadow: "0 0 16px #22c55e88",
        color: "#bbf7d0",
      };
    case "done":
      return {
        background: "#14532d",
        border: "2px solid #4ade80",
        color: "#dcfce7",
      };
    default:
      return {
        background: "#1f2937",
        border: "2px solid #374151",
        color: "#9ca3af",
      };
  }
}

interface Props {
  agentStates: Record<string, AgentState>;
  activeEdges: Set<string>;
}

export function AgentFlowGraph({ agentStates, activeEdges }: Props) {
  const nodes: Node[] = NODE_DEFS.map((n) => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: {
      label: (
        <div className="px-3 py-2 min-w-[110px] text-center text-sm font-medium">
          <div className="text-xl mb-1">{n.emoji}</div>
          <div>{n.label}</div>
          {agentStates[n.id]?.status === "running" && (
            <div className="text-xs mt-1 animate-pulse text-green-400">running…</div>
          )}
          {agentStates[n.id]?.status === "done" && (
            <div className="text-xs mt-1 text-green-300">✓ done</div>
          )}
        </div>
      ),
    },
    style: nodeStyle(agentStates[n.id]?.status),
    className: "rounded-xl",
  }));

  const edges: Edge[] = EDGE_DEFS.map((e) => {
    const key = `${e.source}->${e.target}`;
    const isActive = activeEdges.has(key);
    return {
      id: key,
      source: e.source,
      target: e.target,
      animated: isActive,
      style: {
        stroke: isActive ? "#22c55e" : "#374151",
        strokeWidth: isActive ? 3 : 1.5,
        filter: isActive ? "drop-shadow(0 0 4px #22c55e)" : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isActive ? "#22c55e" : "#374151",
      },
    };
  });

  return (
    <div className="w-full h-[540px] rounded-2xl overflow-hidden border border-gray-800 bg-gray-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1f2937" gap={24} />
        <Controls
          style={{ background: "#111827", border: "1px solid #374151" }}
        />
        <Panel position="top-left">
          <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-400">
            <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1.5 animate-pulse" />
            Edges glow on data handoff
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
