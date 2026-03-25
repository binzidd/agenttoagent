import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { SolarResult, BatteryResult } from "../types";

interface Props {
  solar: SolarResult;
  battery: BatteryResult;
}

const MODE_COLOR = {
  GRID_EXPORT: "text-green-400",
  SOLAR_SOAK:  "text-yellow-400",
  PRESERVE:    "text-blue-400",
};

export function SolarCard({ solar, battery }: Props) {
  const chartData = solar.hourly_radiation.map((val, i) => ({
    hour: `${i}:00`,
    "Solar W/m²": Math.round(val),
    "Cloud %": solar.hourly_cloud[i],
  }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">☀️</span>
        <h3 className="font-semibold text-white">Solar & Battery</h3>
        <span
          className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-full ${
            solar.status === "HIGH"
              ? "bg-green-900 text-green-300"
              : solar.status === "MEDIUM"
              ? "bg-yellow-900 text-yellow-300"
              : "bg-gray-800 text-gray-400"
          }`}
        >
          {solar.status}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <Stat label="Today yield" value={`${solar.forecast_yield_kwh_today} kWh`} />
        <Stat label="Tomorrow" value={`${solar.forecast_yield_kwh_tomorrow} kWh`} />
        <Stat label="Peak gen" value={`${solar.peak_generation_hour}:00`} />
        <Stat label="Avg cloud" value={`${solar.avg_cloud_cover_pct}%`} />
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="solarGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#eab308" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="hour" tick={{ fontSize: 10, fill: "#6b7280" }} interval={5} />
          <YAxis hide />
          <Tooltip
            contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
            labelStyle={{ color: "#9ca3af" }}
          />
          <Area
            type="monotone"
            dataKey="Solar W/m²"
            stroke="#eab308"
            fill="url(#solarGrad)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Battery */}
      <div className="mt-4 pt-4 border-t border-gray-800">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400">Battery strategy</span>
          <span className={`text-xs font-bold ${MODE_COLOR[battery.mode]}`}>
            {battery.mode.replace("_", " ")}
          </span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2">
          <div
            className="h-2 rounded-full bg-green-500 transition-all"
            style={{ width: `${battery.estimated_battery_fill_pct}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-2">{battery.detail}</p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-800 rounded-lg px-3 py-2">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-semibold text-white mt-0.5">{value}</p>
    </div>
  );
}
