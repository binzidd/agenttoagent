# 🏡 Austral Agent Stack

A multi-agent AI system for cost optimisation in Austral, NSW — managing a **9 kWh SolarEdge home battery** and a **Yamaha MT-10 motorcycle**.

The system runs 8 specialised agents concurrently + sequentially, streaming real-time trace events to a React UI that visualises the agent communication graph as it happens.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
│   Concurrent ────────────────────────────────────────────────   │
│   ☀  SolarAnalyst    ⛽ FuelScout   🌐 MacroGeopolitics  🌤 Ride │
│   Sequential ────────────────────────────────────────────────   │
│   SolarAnalyst → BatteryManager → GridArbitrage                 │
│   FuelScout    → Logistics      → MT10Calculator                │
└─────────────────────────────────────────────────────────────────┘
              │  WebSocket (real-time trace events)
              ▼
        React UI (ReactFlow graph + live trace log + data cards)
```

## Agents

| Agent | Purpose | API |
|---|---|---|
| **SolarAnalyst** | 24 h solar irradiance + kWh yield forecast | Open-Meteo (free) |
| **BatteryManager** | GRID_EXPORT / SOLAR_SOAK / PRESERVE strategy | Pure logic |
| **GridArbitrage** ⭐ | NSW NEM spot price → EXPORT / STORE / CONSUME | AEMO (free) |
| **FuelScout** | Cheapest P98 within 20 km | NSW FuelCheck API + fallback |
| **Logistics** | Riding distance from home to pump | OSRM (free) |
| **MT10Calculator** | Is the detour profitable? | Pure math |
| **MacroGeopolitics** | Brent Crude + AUD/USD live price + trend | Yahoo Finance (free) |
| **RideScout** ⭐ | Best ride window today (0–100 score) | Open-Meteo (free) |

⭐ = new agents added in v2

---

## Quick Start (localhost)

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (Optional) Copy and edit env file
cp .env.example .env

# Start server
python api.py
# → http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Open **http://localhost:5173** and click **▶ Run Analysis**.

---

## Environment Variables

All values have sensible defaults — the stack works out of the box with **no API keys** required.

| Variable | Default | Description |
|---|---|---|
| `NSW_FUELCHECK_API_KEY` | *(empty)* | [Register free](https://api.nsw.gov.au/Product/Index/22) for live fuel prices |
| `NSW_FUELCHECK_API_SECRET` | *(empty)* | Paired with API key |
| `HOME_LAT` | `-33.93` | Home latitude |
| `HOME_LON` | `150.82` | Home longitude |
| `HOME_POSTCODE` | `2179` | Fuel search postcode |
| `SOLAR_SYSTEM_KW` | `9.0` | Installed solar capacity |
| `BATTERY_CAPACITY_KWH` | `9.0` | Home battery capacity |
| `FEED_IN_TARIFF_CENTS` | `5.0` | c/kWh for grid export |
| `BIKE_CONSUMPTION_L_100KM` | `7.5` | Fuel consumption |
| `BIKE_TANK_FILL_LITRES` | `15.0` | Typical fill volume |

Copy `backend/.env.example` → `backend/.env` and override any values.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/solar` | Solar forecast |
| `GET` | `/api/fuel` | Fuel prices |
| `GET` | `/api/ride` | Ride score & window |
| `GET` | `/api/grid` | NEM spot + arbitrage advice |
| `GET` | `/api/analysis` | Full blocking analysis |
| `WS` | `/ws` | Real-time trace stream |

### WebSocket protocol

```js
// Send to trigger analysis
ws.send(JSON.stringify({ action: "run" }))

// Receive trace events (multiple, streamed)
{ type: "trace", event: "agent_start"|"agent_complete"|"handoff"|..., agent: "SolarAnalyst", data: {...}, timestamp: "..." }

// Receive final result (once)
{ type: "complete", data: { solar, battery, grid, fuel_pumps, route, decision, macro, ride } }
```

---

## Data Sources

All external data is fetched live from public APIs — nothing is hardcoded:

| Data | Source | Key required? |
|---|---|---|
| Solar irradiance | [Open-Meteo](https://open-meteo.com/) | No |
| Ride weather | [Open-Meteo](https://open-meteo.com/) | No |
| Routing / distance | [OSRM](http://router.project-osrm.org/) | No |
| Brent Crude / AUD/USD | Yahoo Finance (`yfinance`) | No |
| NEM electricity spot | [AEMO public API](https://aemo.com.au/) | No |
| P98 fuel prices | [NSW FuelCheck](https://api.nsw.gov.au/) | Optional |

---

## Project Structure

```
agenttoagent/
├── backend/
│   ├── agents/
│   │   ├── solar_analyst.py      # Open-Meteo solar forecast
│   │   ├── battery_manager.py    # Charge/discharge strategy
│   │   ├── grid_arbitrage.py     # ⭐ NEM spot price arbitrage
│   │   ├── fuel_scout.py         # NSW FuelCheck / fallback
│   │   ├── logistics.py          # OSRM routing
│   │   ├── mt10_calculator.py    # Detour profitability
│   │   ├── macro_geopolitics.py  # Brent + AUD/USD via yfinance
│   │   └── ride_scout.py         # ⭐ Best ride window scorer
│   ├── infra/
│   │   ├── agent_config.yaml     # Agent manifest
│   │   └── guardrails.cedar      # Cedar security policy
│   ├── api.py                    # FastAPI + WebSocket server
│   ├── orchestrator.py           # Agent sequencing + trace events
│   ├── config.py                 # Pydantic settings from env
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── AgentFlowGraph.tsx  # ReactFlow real-time graph
│       │   ├── TracePanel.tsx      # Live event log
│       │   ├── SolarCard.tsx       # Solar + battery data
│       │   ├── FuelCard.tsx        # Fuel prices + decision
│       │   ├── RideCard.tsx        # Ride score radar
│       │   └── GridCard.tsx        # NEM arbitrage card
│       ├── hooks/useAgentSocket.ts # WebSocket + state management
│       ├── types/index.ts          # Shared TypeScript types
│       └── App.tsx
└── README.md
```
