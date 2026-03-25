import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import type { RideResult } from "../types";

interface Props {
  ride: RideResult;
}

function scoreColor(score: number) {
  if (score >= 70) return "text-green-400";
  if (score >= 45) return "text-yellow-400";
  if (score >= 20) return "text-orange-400";
  return "text-gray-500";
}

export function RideCard({ ride }: Props) {
  const { overall_day_score, best_window_start, recommendation, hourly_scores } = ride;

  // Build radar data from the best hour
  const best = hourly_scores.find((h) => h.score === Math.max(...hourly_scores.map((x) => x.score)));
  const radarData = best
    ? [
        { subject: "Temp", value: best.temp_c != null ? Math.min(100, ((best.temp_c - 5) / 25) * 100) : 50 },
        { subject: "Wind", value: best.wind_kmh != null ? Math.max(0, 100 - best.wind_kmh * 2) : 50 },
        { subject: "Dry", value: best.rain_prob_pct != null ? 100 - best.rain_prob_pct : 50 },
        { subject: "Clear", value: best.cloud_pct != null ? 100 - best.cloud_pct : 50 },
      ]
    : [];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">🏍️</span>
        <h3 className="font-semibold text-white">Ride Scout</h3>
        <span className={`ml-auto text-2xl font-bold ${scoreColor(overall_day_score)}`}>
          {overall_day_score.toFixed(0)}
          <span className="text-sm text-gray-500">/100</span>
        </span>
      </div>

      <p className="text-sm text-gray-300 mb-4">{recommendation}</p>

      {best_window_start != null && (
        <div className="bg-gray-800 rounded-xl px-4 py-2 mb-4 text-sm">
          <span className="text-gray-400">Best window: </span>
          <span className="text-white font-semibold">
            {best_window_start}:00 – {best_window_start + 2}:00
          </span>
        </div>
      )}

      {radarData.length > 0 && (
        <ResponsiveContainer width="100%" height={160}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "#9ca3af" }} />
            <Radar
              name="Conditions"
              dataKey="value"
              stroke="#22c55e"
              fill="#22c55e"
              fillOpacity={0.25}
            />
          </RadarChart>
        </ResponsiveContainer>
      )}

      {/* Hourly bar strip */}
      <div className="flex gap-0.5 mt-3">
        {hourly_scores.slice(6, 22).map((h) => (
          <div key={h.hour} className="flex-1 flex flex-col items-center gap-0.5">
            <div
              className="w-full rounded-sm transition-all"
              style={{
                height: `${Math.max(3, (h.score / 100) * 36)}px`,
                background:
                  h.score >= 70 ? "#22c55e" : h.score >= 45 ? "#eab308" : "#374151",
              }}
            />
            <span className="text-[9px] text-gray-600">{h.hour}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
