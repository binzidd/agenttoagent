import { useState, useRef, useCallback } from "react";
import type {
  WsMessage,
  TraceMessage,
  AnalysisResult,
  AgentStatus,
} from "../types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";

export interface AgentState {
  status: AgentStatus;
  data: Record<string, unknown> | null;
}

export function useAgentSocket() {
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(false);
  const [traces, setTraces] = useState<TraceMessage[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>(
    {}
  );
  const [activeEdges, setActiveEdges] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const ws = useRef<WebSocket | null>(null);

  const updateAgent = useCallback(
    (agent: string, status: AgentStatus, data?: Record<string, unknown>) => {
      setAgentStates((prev) => ({
        ...prev,
        [agent]: { status, data: data ?? prev[agent]?.data ?? null },
      }));
    },
    []
  );

  const handleMessage = useCallback(
    (msg: WsMessage) => {
      if (msg.type === "trace") {
        setTraces((prev) => [...prev, msg]);

        switch (msg.event) {
          case "workflow_start":
            updateAgent("Orchestrator", "running");
            break;

          case "agent_start":
            updateAgent(msg.agent, "running");
            break;

          case "agent_complete":
            updateAgent(msg.agent, "done", msg.data);
            break;

          case "handoff":
            if (msg.target) {
              const edgeKey = `${msg.agent}->${msg.target}`;
              setActiveEdges((prev) => new Set(prev).add(edgeKey));
              // Remove after animation
              setTimeout(() => {
                setActiveEdges((prev) => {
                  const next = new Set(prev);
                  next.delete(edgeKey);
                  return next;
                });
              }, 2000);
            }
            break;

          case "workflow_complete":
            updateAgent("Orchestrator", "done");
            break;
        }
      } else if (msg.type === "complete") {
        setResult(msg.data);
        setRunning(false);
      } else if (msg.type === "error") {
        setError(msg.message);
        setRunning(false);
      }
    },
    [updateAgent]
  );

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    const socket = new WebSocket(WS_URL);
    ws.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => {
      setConnected(false);
      setRunning(false);
    };
    socket.onerror = () => setError("WebSocket connection failed.");
    socket.onmessage = (e) => {
      try {
        handleMessage(JSON.parse(e.data) as WsMessage);
      } catch {
        // ignore malformed frames
      }
    };
  }, [handleMessage]);

  const runAnalysis = useCallback(() => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      connect();
      // Give the socket a moment to open then send
      setTimeout(() => {
        ws.current?.send(JSON.stringify({ action: "run" }));
      }, 200);
      return;
    }

    // Reset state
    setTraces([]);
    setResult(null);
    setError(null);
    setAgentStates({});
    setActiveEdges(new Set());
    setRunning(true);

    ws.current.send(JSON.stringify({ action: "run" }));
  }, [connect]);

  return {
    connected,
    running,
    traces,
    result,
    agentStates,
    activeEdges,
    error,
    connect,
    runAnalysis,
  };
}
