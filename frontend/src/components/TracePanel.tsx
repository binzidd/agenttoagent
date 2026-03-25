/**
 * TracePanel – scrollable real-time log of agent trace events.
 */
import { useEffect, useRef } from "react";
import type { TraceMessage } from "../types";

const EVENT_COLORS: Record<string, string> = {
  workflow_start:    "text-blue-400",
  workflow_complete: "text-green-400",
  agent_start:       "text-yellow-400",
  agent_complete:    "text-green-400",
  handoff:           "text-purple-400",
};

const EVENT_ICON: Record<string, string> = {
  workflow_start:    "▶",
  workflow_complete: "✓",
  agent_start:       "◉",
  agent_complete:    "●",
  handoff:           "→",
};

interface Props {
  traces: TraceMessage[];
  running: boolean;
}

export function TracePanel({ traces, running }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [traces.length]);

  return (
    <div className="flex flex-col h-full bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-sm font-semibold text-gray-300">Trace Log</span>
        {running && (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
        )}
        {!running && traces.length > 0 && (
          <span className="text-xs text-gray-500">{traces.length} events</span>
        )}
      </div>

      {/* Log */}
      <div className="flex-1 overflow-y-auto trace-scroll p-3 space-y-1 font-mono text-xs">
        {traces.length === 0 && (
          <div className="text-gray-600 text-center mt-8">
            Click "Run Analysis" to start
          </div>
        )}
        {traces.map((t, i) => (
          <div key={i} className="flex gap-2 items-start">
            <span className="text-gray-600 select-none w-16 shrink-0">
              {new Date(t.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <span
              className={`shrink-0 ${EVENT_COLORS[t.event] ?? "text-gray-400"}`}
            >
              {EVENT_ICON[t.event] ?? "·"}
            </span>
            <span className="text-gray-300">
              <span className="text-white font-semibold">{t.agent}</span>
              {t.target && (
                <>
                  <span className="text-gray-500"> → </span>
                  <span className="text-purple-300">{t.target}</span>
                </>
              )}
              <span className="text-gray-500"> [{t.event}]</span>
              {t.event === "agent_complete" && t.data && (
                <span className="text-gray-500 ml-1">
                  {summarise(t.data)}
                </span>
              )}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function summarise(data: Record<string, unknown>): string {
  // Show a 1-line summary of the most interesting field
  if ("forecast_yield_kwh_today" in data)
    return `→ ${data.forecast_yield_kwh_today} kWh today`;
  if ("net_profit" in data)
    return `→ net ${data.profitable ? "+" : ""}$${data.net_profit}`;
  if ("recommended_action" in data)
    return `→ ${data.recommended_action}`;
  if ("recommendation" in data && typeof data.recommendation === "string")
    return `→ ${(data.recommendation as string).slice(0, 50)}`;
  if ("mode" in data) return `→ ${data.mode}`;
  if ("crude_trend" in data) return `→ Brent ${data.crude_trend}`;
  if (Array.isArray(data)) return `→ ${(data as unknown[]).length} stations`;
  return "";
}
