# 🏡 Austral Agent Stack

A multi-agent AI system for cost optimisation in Austral, NSW — managing a **9 kWh SolarEdge home battery** and a **Yamaha MT-10 motorcycle**. Powered by Claude claude-sonnet-4-6, with a live Streamlit dashboard and AWS Bedrock AgentCore-compatible backend.

---

## Table of Contents

- [Architecture](#architecture)
- [Agents](#agents)
- [Prerequisites](#prerequisites)
- [Quick Start — Streamlit Dashboard](#quick-start--streamlit-dashboard)
- [Quick Start — FastAPI + React](#quick-start--fastapi--react-optional)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [AWS Bedrock AgentCore Deployment](#aws-bedrock-agentcore-deployment)
- [Project Structure](#project-structure)
- [Data Sources](#data-sources)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                           Orchestrator                                 │
│                                                                        │
│  Concurrent ──────────────────────────────────────────────────────    │
│  ☀ SolarAnalyst   ⛽ FuelScout   🌐 MacroGeopolitics   🌤 RideScout   │
│                                                                        │
│  Sequential ──────────────────────────────────────────────────────    │
│  SolarAnalyst → BatteryManager → GridArbitrage                        │
│  FuelScout    → Logistics      → MT10Calculator                       │
│  All agents   → ClaudeAdvisor (LLM synthesis)                         │
└────────────────────────────────────────────────────────────────────────┘
         │
         ├── Streamlit dashboard  (localhost:8501)
         ├── FastAPI + WebSocket  (localhost:8000)   [optional]
         └── AWS Bedrock AgentCore                   [production]
```

---

## Agents

| Agent | Role | API Used | Key Required |
|---|---|---|---|
| **SolarAnalyst** | 24h solar irradiance + kWh yield forecast | Open-Meteo | No |
| **BatteryManager** | GRID_EXPORT / SOLAR_SOAK / PRESERVE strategy | None (logic) | No |
| **GridArbitrage** ⭐ | NSW NEM spot price → EXPORT / STORE / CONSUME | AEMO public | No |
| **FuelScout** | Cheapest P98 within 20 km | NSW FuelCheck | Optional |
| **Logistics** | Riding distance from home to pump | OSRM | No |
| **MT10Calculator** | Is the detour profitable after fuel cost? | None (math) | No |
| **MacroGeopolitics** | Live Brent Crude + AUD/USD, trend sentiment | Yahoo Finance | No |
| **RideScout** ⭐ | Hourly ride score (0–100) + best window | Open-Meteo | No |
| **ClaudeAdvisor** ⭐ | LLM synthesis of all agent outputs | Anthropic | Yes |

⭐ = new in v2

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9 – 3.11 | 3.10 recommended |
| pip | Any | Ships with Python |
| Node.js | 18+ | Only needed for React frontend |
| AWS CLI | 2.x | Only needed for AgentCore deployment |
| Docker | 24+ | Only needed for AgentCore deployment |

---

## Quick Start — Streamlit Dashboard

This is the primary interface. No Node.js required.

### Step 1 — Clone and enter the repo

```bash
git clone https://github.com/binzidd/agenttoagent.git
cd agenttoagent
```

### Step 2 — Install Python dependencies

**Option A: Anaconda (recommended if you already use Anaconda)**

```bash
pip install -r backend/requirements.txt
```

**Option B: Virtual environment**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Configure environment

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in your keys:

```ini
# Required for chat + Claude synthesis
ANTHROPIC_API_KEY=sk-ant-...

# Optional — leave blank to use realistic synthetic fallback
NSW_FUELCHECK_API_KEY=
NSW_FUELCHECK_API_SECRET=
```

All other values have sensible defaults for Austral, NSW. You can leave them as-is.

### Step 4 — Run the dashboard

```bash
# If using Anaconda:
cd backend
streamlit run dashboard.py

# If using venv:
cd backend
source .venv/bin/activate
streamlit run dashboard.py
```

Open **http://localhost:8501** and click **▶ Run Analysis**.

> **Tip:** Streamlit hot-reloads on file save. You can edit any agent and see changes immediately.

---

## Quick Start — FastAPI + React (Optional)

The React frontend provides the real-time WebSocket agent flow graph. It is optional — the Streamlit dashboard has equivalent functionality.

### Terminal 1 — Backend API

```bash
cd backend
source .venv/bin/activate   # or Anaconda
python api.py
# Server starts at http://localhost:8000
```

### Terminal 2 — React Frontend

```bash
cd frontend
npm install
npm run dev
# App starts at http://localhost:5173
```

---

## Environment Variables

All configuration is loaded from `backend/.env`. Copy from `backend/.env.example` to get started.

| Variable | Default | Required | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Yes** | Powers chat and Claude synthesis. Get at [console.anthropic.com](https://console.anthropic.com) |
| `NSW_FUELCHECK_API_KEY` | — | No | Live NSW fuel prices. [Register free](https://api.nsw.gov.au/Product/Index/22). Falls back to synthetic data if absent. |
| `NSW_FUELCHECK_API_SECRET` | — | No | Paired with API key |
| `HOME_LAT` | `-33.93` | No | Home latitude (Austral NSW default) |
| `HOME_LON` | `150.82` | No | Home longitude |
| `HOME_POSTCODE` | `2179` | No | Fuel search postcode |
| `SOLAR_SYSTEM_KW` | `9.0` | No | Installed solar panel capacity (kW) |
| `BATTERY_CAPACITY_KWH` | `9.0` | No | Home battery capacity (kWh) |
| `FEED_IN_TARIFF_CENTS` | `5.0` | No | Solar export rate (c/kWh) |
| `BIKE_CONSUMPTION_L_100KM` | `7.5` | No | MT-10 fuel consumption |
| `BIKE_TANK_FILL_LITRES` | `15.0` | No | Typical fill volume |
| `PREFERRED_FUEL_TYPE` | `P98` | No | Fuel grade to search |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | No | CORS origins for FastAPI |

---

## API Reference

The FastAPI server (`backend/api.py`) exposes these endpoints when running:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — `{"status":"ok"}` |
| `GET` | `/api/solar` | Live solar forecast from Open-Meteo |
| `GET` | `/api/fuel` | P98 prices (live or synthetic) |
| `GET` | `/api/ride` | Today's ride window score |
| `GET` | `/api/grid?battery_fill_pct=50` | NEM spot price + arbitrage advice |
| `GET` | `/api/analysis` | Full blocking analysis (all agents) |
| `POST` | `/api/chat` | Streaming SSE chat powered by Claude |
| `WS` | `/ws` | Real-time trace event stream |

### WebSocket protocol

```js
// Client → Server: trigger analysis
ws.send(JSON.stringify({ action: "run" }))

// Server → Client: trace events (multiple, streamed in real-time)
{ "type": "trace", "event": "agent_start"|"agent_complete"|"handoff", "agent": "SolarAnalyst", "data": {}, "timestamp": "..." }

// Server → Client: final result (once, when all agents complete)
{ "type": "complete", "data": { solar, battery, grid, fuel_pumps, route, decision, macro, ride, summary } }
```

### Chat endpoint

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Should I ride today?"}]}'
```

Response is `text/event-stream` (SSE):
```
data: "Based"
data: " on"
data: " today's"
...
data: [DONE]
```

---

## AWS Bedrock AgentCore Deployment

The `backend/main.py` follows the AWS Bedrock AgentCore container spec. Deploying creates a managed, scalable agent endpoint without managing servers.

### Prerequisites for deployment

- AWS CLI configured (`aws configure`)
- Docker installed and running
- IAM permissions: `bedrock:InvokeAgent`, `ecr:*`, `agentcore:*`

### Step 1 — Build and test the container locally

```bash
# Build
docker build -t austral-agent-stack .

# Test locally (replace with your real key)
docker run -p 8080:8080 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e HOME_LAT=-33.93 \
  -e HOME_LON=150.82 \
  austral-agent-stack

# Test the entrypoint
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{"action": "full_analysis"}'
```

### Step 2 — Push to Amazon ECR

```bash
# Set your AWS account and region
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-southeast-2   # Sydney

# Create the ECR repository
aws ecr create-repository \
  --repository-name austral-agent-stack \
  --region $AWS_REGION

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS \
    --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag austral-agent-stack:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/austral-agent-stack:latest

docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/austral-agent-stack:latest
```

### Step 3 — Create the AgentCore agent

```bash
# Store secrets in AWS Secrets Manager (never hardcode in container)
aws secretsmanager create-secret \
  --name austral/anthropic-api-key \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-..."}'

aws secretsmanager create-secret \
  --name austral/fuelcheck-api \
  --secret-string '{"NSW_FUELCHECK_API_KEY":"...","NSW_FUELCHECK_API_SECRET":"..."}'

# Deploy to AgentCore (via AWS Console or CLI)
# Console path: AWS → Bedrock → AgentCore → Create Agent
#   - Container image: <your ECR URI>
#   - Environment variables: reference the Secrets Manager ARNs above
#   - Memory: 512 MB minimum
#   - Timeout: 60 seconds (agents make multiple API calls)
```

### Step 4 — Configure the Streamlit dashboard to use AgentCore

Once deployed, update `backend/.env` to point at your AgentCore endpoint:

```ini
# AgentCore endpoint (replaces local orchestrator calls when set)
AGENTCORE_ENDPOINT=https://bedrock-agentcore.<region>.amazonaws.com/agents/<agent-id>/agentAliases/<alias-id>/sessions/-/text
AGENTCORE_REGION=ap-southeast-2
```

### AgentCore payload schema

```json
{
  "action":   "full_analysis | chat | solar | fuel | ride | grid",
  "prompt":   "Optional natural language question",
  "messages": [{"role": "user", "content": "..."}],
  "context":  {}
}
```

### AgentCore response schema

```json
{
  "status":  "SUCCESS | ERROR",
  "action":  "full_analysis",
  "result":  { "solar": {}, "battery": {}, "grid": {}, "fuel_pumps": [], "decision": {}, "macro": {}, "ride": {} },
  "summary": "Plain English summary from ClaudeAdvisor"
}
```

---

## Project Structure

```
agenttoagent/
├── Dockerfile                    # AgentCore-compatible container spec
├── README.md
├── .gitignore
│
├── backend/
│   ├── dashboard.py              # ★ Streamlit dashboard (primary UI)
│   ├── main.py                   # ★ AWS AgentCore entry point
│   ├── api.py                    # FastAPI + WebSocket server
│   ├── orchestrator.py           # Agent sequencing + trace events
│   ├── config.py                 # Pydantic settings (reads from .env)
│   ├── requirements.txt          # All Python dependencies
│   ├── .env                      # ← your secrets (gitignored)
│   ├── .env.example              # Template — copy to .env
│   ├── .streamlit/
│   │   └── config.toml           # Dark green theme
│   ├── agents/
│   │   ├── solar_analyst.py      # Open-Meteo solar forecast
│   │   ├── battery_manager.py    # Charge/discharge strategy logic
│   │   ├── grid_arbitrage.py     # AEMO NEM spot price arbitrage
│   │   ├── fuel_scout.py         # NSW FuelCheck + synthetic fallback
│   │   ├── logistics.py          # OSRM open routing
│   │   ├── mt10_calculator.py    # Detour profitability math
│   │   ├── macro_geopolitics.py  # Brent Crude + AUD/USD via yfinance
│   │   ├── ride_scout.py         # Hourly weather ride scorer
│   │   └── claude_advisor.py     # LLM synthesis (Claude claude-sonnet-4-6)
│   └── infra/
│       ├── agent_config.yaml     # Agent manifest
│       └── guardrails.cedar      # Cedar security policy
│
├── frontend/                     # React app (optional — Streamlit is primary)
│   └── src/
│       ├── components/
│       │   ├── AgentFlowGraph.tsx  # ReactFlow real-time graph
│       │   ├── TracePanel.tsx      # Live event log
│       │   ├── SolarCard.tsx
│       │   ├── FuelCard.tsx
│       │   ├── RideCard.tsx
│       │   ├── GridCard.tsx
│       │   └── ChatPanel.tsx       # Streaming Claude chat
│       ├── hooks/useAgentSocket.ts
│       ├── types/index.ts
│       └── App.tsx
│
└── austral-agent-app/            # Original proof-of-concept (reference only)
```

---

## Data Sources

| Data | Provider | API Key | Docs |
|---|---|---|---|
| Solar irradiance | Open-Meteo | None | [open-meteo.com](https://open-meteo.com) |
| Weather / ride conditions | Open-Meteo | None | [open-meteo.com](https://open-meteo.com) |
| Driving distance | OSRM | None | [project-osrm.org](http://project-osrm.org) |
| Brent Crude + FX | Yahoo Finance | None | via `yfinance` |
| NEM electricity spot | AEMO | None | [aemo.com.au](https://aemo.com.au) |
| P98 fuel prices | NSW FuelCheck | Optional | [api.nsw.gov.au](https://api.nsw.gov.au/Product/Index/22) |
| LLM synthesis + chat | Anthropic Claude | **Required** | [console.anthropic.com](https://console.anthropic.com) |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'pydantic_settings'`

You're running Streamlit from a Python environment that's missing the dependencies.

```bash
# Install into whichever Python is running Streamlit:
pip install pydantic-settings httpx yfinance anthropic plotly

# Or explicitly use the project venv:
cd backend
source .venv/bin/activate
streamlit run dashboard.py
```

### `ModuleNotFoundError: No module named 'streamlit'` or old Streamlit (< 1.31)

```bash
pip install "streamlit>=1.43.0"
```

### Chat returns "⚠️ Set ANTHROPIC_API_KEY"

Add your key to `backend/.env`:
```ini
ANTHROPIC_API_KEY=sk-ant-...
```

### Fuel prices show `(est.)` badge

No NSW FuelCheck API key is configured. The app falls back to synthetic prices that vary slightly with time of day. [Register free](https://api.nsw.gov.au/Product/Index/22) to get live data.

### Brent Crude shows "Using fallback market data"

`yfinance` couldn't reach Yahoo Finance (network issue or rate limit). The app uses last-known typical values as a fallback.

### AgentCore: container exits immediately

- Check that `CMD ["python", "main.py"]` is in the Dockerfile
- Verify the `bedrock-agentcore` package is installed inside the container
- Check CloudWatch logs for the specific Python error

### OSRM routing returns an error

The free OSRM demo server (`router.project-osrm.org`) has occasional downtime. The logistics agent will raise an exception — the dashboard will still load using the last successful result.
