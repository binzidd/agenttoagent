import { useEffect } from "react";
import { AgentFlowGraph } from "./components/AgentFlowGraph";
import { TracePanel } from "./components/TracePanel";
import { SolarCard } from "./components/SolarCard";
import { FuelCard } from "./components/FuelCard";
import { RideCard } from "./components/RideCard";
import { GridCard } from "./components/GridCard";
import { useAgentSocket } from "./hooks/useAgentSocket";

export default function App() {
  const { connected, running, traces, result, agentStates, activeEdges, error, connect, runAnalysis } =
    useAgentSocket();

  // Auto-connect on mount
  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6" style={{ maxWidth: "100%" }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto mb-6 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            🏡 Austral Agent Stack
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Multi-agent cost optimisation · Austral NSW · Solar + Fuel + Ride
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span
              className={`w-2 h-2 rounded-full ${
                connected ? "bg-green-500 animate-pulse" : "bg-red-500"
              }`}
            />
            {connected ? "Connected" : "Disconnected"}
          </div>

          <button
            onClick={runAnalysis}
            disabled={running}
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              running
                ? "bg-gray-700 text-gray-400 cursor-not-allowed"
                : "bg-green-600 hover:bg-green-500 text-white shadow-lg shadow-green-900/50"
            }`}
          >
            {running ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                Running…
              </span>
            ) : (
              "▶ Run Analysis"
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="max-w-[1400px] mx-auto mb-4 bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-300">
          ⚠ {error}
        </div>
      )}

      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* ── Row 1: Flow graph + Trace panel ─────────────────────────── */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <AgentFlowGraph agentStates={agentStates} activeEdges={activeEdges} />
          </div>
          <div className="h-[540px]">
            <TracePanel traces={traces} running={running} />
          </div>
        </div>

        {/* ── Row 2: Data cards ────────────────────────────────────────── */}
        {result && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              <SolarCard solar={result.solar} battery={result.battery} />
              <FuelCard
                pumps={result.fuel_pumps}
                bestPump={result.best_pump}
                route={result.route}
                decision={result.decision}
                macro={result.macro}
              />
              <RideCard ride={result.ride} />
              <GridCard grid={result.grid} />
            </div>

            {/* ── Decision banner ──────────────────────────────────────── */}
            <div
              className={`rounded-2xl border px-6 py-5 flex items-center gap-4 flex-wrap ${
                result.decision.profitable
                  ? "bg-green-900/30 border-green-700"
                  : "bg-gray-800/50 border-gray-700"
              }`}
            >
              <span className="text-4xl">
                {result.decision.profitable ? "🟢" : "🔴"}
              </span>
              <div>
                <p className="text-xl font-bold text-white">
                  {result.decision.profitable
                    ? "GO – Head to " + result.best_pump.name
                    : "STAY – Not worth the ride"}
                </p>
                <p className="text-sm text-gray-400 mt-0.5">{result.decision.logic}</p>
              </div>
              {result.decision.profitable && (
                <div className="ml-auto text-right">
                  <p className="text-xs text-gray-500">Net saving</p>
                  <p className="text-2xl font-bold text-green-400">
                    +${result.decision.net_profit.toFixed(2)}
                  </p>
                </div>
              )}
            </div>
          </>
        )}

        {!result && !running && (
          <div className="text-center py-20 text-gray-600">
            <p className="text-5xl mb-4">🤖</p>
            <p className="text-lg">Press "Run Analysis" to activate all agents</p>
            <p className="text-sm mt-1">Watch the flow graph animate in real-time</p>
          </div>
        )}
      </div>
    </div>
  );
}
