// ─── WebSocket message types ──────────────────────────────────────────────────

export type TraceEvent =
  | "agent_start"
  | "agent_data"
  | "agent_complete"
  | "handoff"
  | "workflow_start"
  | "workflow_complete";

export interface TraceMessage {
  type: "trace";
  event: TraceEvent;
  agent: string;
  target?: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface CompleteMessage {
  type: "complete";
  data: AnalysisResult;
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export type WsMessage = TraceMessage | CompleteMessage | ErrorMessage;

// ─── Agent names (canonical) ─────────────────────────────────────────────────

export const AGENT_IDS = [
  "Orchestrator",
  "SolarAnalyst",
  "BatteryManager",
  "GridArbitrage",
  "FuelScout",
  "Logistics",
  "MT10Calculator",
  "MacroGeopolitics",
  "RideScout",
] as const;

export type AgentId = (typeof AGENT_IDS)[number];

export type AgentStatus = "idle" | "running" | "done" | "error";

// ─── Analysis result types ───────────────────────────────────────────────────

export interface SolarResult {
  radiation_mj_today: number;
  forecast_yield_kwh_today: number;
  forecast_yield_kwh_tomorrow: number;
  peak_generation_hour: number;
  avg_cloud_cover_pct: number;
  status: "HIGH" | "MEDIUM" | "LOW";
  hourly_radiation: number[];
  hourly_cloud: number[];
}

export interface BatteryResult {
  mode: "GRID_EXPORT" | "SOLAR_SOAK" | "PRESERVE";
  excess_solar_kwh: number;
  estimated_battery_fill_pct: number;
  detail: string;
}

export interface GridResult {
  nem_spot_cents_kwh: number;
  feed_in_tariff_cents: number;
  recommended_action: "EXPORT" | "STORE" | "CONSUME";
  reason: string;
  estimated_value_cents_kwh: number;
  data_source: string;
  period?: string;
}

export interface FuelStation {
  name: string;
  brand: string;
  address: string;
  price: number;
  lat: number;
  lon: number;
  source?: string;
}

export interface RouteResult {
  distance_km: number;
  duration_min: number;
  round_trip_km: number;
}

export interface DecisionResult {
  net_profit: number;
  profitable: boolean;
  savings_at_pump: number;
  cost_of_detour: number;
  logic: string;
}

export interface MacroResult {
  brent_crude_usd: number;
  brent_change_pct: number;
  wti_usd: number;
  aud_usd: number;
  crude_trend: "RISING" | "FALLING" | "STABLE";
  recommendation: string;
  data_source: string;
}

export interface HourlyScore {
  hour: number;
  score: number;
  temp_c?: number;
  wind_kmh?: number;
  rain_prob_pct?: number;
  cloud_pct?: number;
}

export interface RideResult {
  overall_day_score: number;
  best_hour: number | null;
  best_window_start: number | null;
  recommendation: string;
  hourly_scores: HourlyScore[];
}

export interface AnalysisResult {
  solar: SolarResult;
  battery: BatteryResult;
  grid: GridResult;
  fuel_pumps: FuelStation[];
  best_pump: FuelStation;
  route: RouteResult;
  decision: DecisionResult;
  macro: MacroResult;
  ride: RideResult;
  summary?: string;
}

// ─── Chat types ───────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}
