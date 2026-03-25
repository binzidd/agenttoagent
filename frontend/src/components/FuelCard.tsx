import type { FuelStation, DecisionResult, RouteResult, MacroResult } from "../types";

interface Props {
  pumps: FuelStation[];
  bestPump: FuelStation;
  route: RouteResult;
  decision: DecisionResult;
  macro: MacroResult;
}

const TREND_COLOR = {
  RISING:  "text-red-400",
  FALLING: "text-green-400",
  STABLE:  "text-gray-400",
};
const TREND_ICON = { RISING: "↑", FALLING: "↓", STABLE: "→" };

export function FuelCard({ pumps, bestPump, route, decision, macro }: Props) {
  const sorted = [...pumps].sort((a, b) => a.price - b.price);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">⛽</span>
        <h3 className="font-semibold text-white">Fuel Intelligence</h3>
        <span
          className={`ml-auto text-sm font-bold px-3 py-1 rounded-full ${
            decision.profitable
              ? "bg-green-900 text-green-300"
              : "bg-red-900 text-red-300"
          }`}
        >
          {decision.profitable ? "GO RIDE" : "STAY HOME"}
        </span>
      </div>

      {/* Decision summary */}
      <div className="bg-gray-800 rounded-xl p-3 mb-4 text-sm">
        <p className="text-gray-300">{decision.logic}</p>
        <div className="flex gap-4 mt-2">
          <span className="text-green-400 text-xs">
            Saved: +${decision.savings_at_pump.toFixed(2)}
          </span>
          <span className="text-red-400 text-xs">
            Detour: -${decision.cost_of_detour.toFixed(2)}
          </span>
          <span className={`text-xs font-bold ${decision.profitable ? "text-green-300" : "text-red-300"}`}>
            Net: {decision.net_profit >= 0 ? "+" : ""}${decision.net_profit.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Route */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <Stat label="Best pump" value={bestPump.name.split(" ").slice(0, 2).join(" ")} />
        <Stat label="Distance" value={`${route.distance_km} km`} />
        <Stat label="Best price" value={`$${bestPump.price.toFixed(3)}/L`} />
      </div>

      {/* Price list */}
      <div className="space-y-1.5 mb-4">
        {sorted.map((s, i) => (
          <div
            key={i}
            className={`flex items-center justify-between text-xs px-3 py-2 rounded-lg ${
              s.name === bestPump.name
                ? "bg-green-900/40 border border-green-800"
                : "bg-gray-800"
            }`}
          >
            <span className="text-gray-300 truncate max-w-[180px]">{s.name}</span>
            <span className={`font-mono font-semibold ${s.name === bestPump.name ? "text-green-300" : "text-gray-200"}`}>
              ${s.price.toFixed(3)}
            </span>
            {s.source === "synthetic" && (
              <span className="text-gray-600 text-[10px] ml-1">est.</span>
            )}
          </div>
        ))}
      </div>

      {/* Macro */}
      <div className="pt-4 border-t border-gray-800">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm">🌐</span>
          <span className="text-xs text-gray-400">Global Energy Market</span>
          <span className={`ml-auto text-xs font-semibold ${TREND_COLOR[macro.crude_trend]}`}>
            {TREND_ICON[macro.crude_trend]} Brent ${macro.brent_crude_usd}
          </span>
        </div>
        <p className="text-xs text-gray-500">{macro.recommendation}</p>
        {macro.data_source === "fallback" && (
          <p className="text-xs text-amber-600 mt-1">⚠ Using fallback market data</p>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-800 rounded-lg px-3 py-2">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xs font-semibold text-white mt-0.5 truncate">{value}</p>
    </div>
  );
}
