import type { GridResult } from "../types";

interface Props {
  grid: GridResult;
}

const ACTION_STYLE = {
  EXPORT: {
    bg: "bg-green-900/40 border-green-800",
    text: "text-green-300",
    icon: "↑",
  },
  STORE: {
    bg: "bg-blue-900/40 border-blue-800",
    text: "text-blue-300",
    icon: "⬇",
  },
  CONSUME: {
    bg: "bg-yellow-900/40 border-yellow-800",
    text: "text-yellow-300",
    icon: "⚡",
  },
};

export function GridCard({ grid }: Props) {
  const style = ACTION_STYLE[grid.recommended_action] ?? ACTION_STYLE.CONSUME;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">⚡</span>
        <h3 className="font-semibold text-white">Grid Arbitrage</h3>
        <span
          className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-full border ${style.bg} ${style.text}`}
        >
          {style.icon} {grid.recommended_action}
        </span>
      </div>

      {/* Prices */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-500">NEM spot price</p>
          <p className="text-lg font-bold text-white mt-0.5">
            {grid.nem_spot_cents_kwh.toFixed(1)}
            <span className="text-xs text-gray-400 ml-1">c/kWh</span>
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg px-3 py-2">
          <p className="text-xs text-gray-500">Feed-in tariff</p>
          <p className="text-lg font-bold text-white mt-0.5">
            {grid.feed_in_tariff_cents.toFixed(1)}
            <span className="text-xs text-gray-400 ml-1">c/kWh</span>
          </p>
        </div>
      </div>

      {/* Reason */}
      <p className="text-sm text-gray-300">{grid.reason}</p>

      <p className="text-xs text-gray-600 mt-3">
        Source: {grid.data_source === "live_aemo" ? "AEMO live" : "TOU estimate"}
        {grid.period && ` · ${grid.period}`}
      </p>
    </div>
  );
}
