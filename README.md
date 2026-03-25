# 🏡 Austral Agent Stack

A multi-agent AI system for cost optimisation in Austral, NSW — managing a **9 kWh SolarEdge home battery** and a **Yamaha MT-10 motorcycle**. Powered by Claude Sonnet, with a live Streamlit dashboard deployed to AWS.

**Live dashboard → [https://d31k8f0371hj3b.cloudfront.net](https://d31k8f0371hj3b.cloudfront.net)**

---

## Table of Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Agents](#agents)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [AWS Deployment — Full Walkthrough](#aws-deployment--full-walkthrough)
- [Observability — Tracing in CloudWatch](#observability--tracing-in-cloudwatch)
- [Project Structure](#project-structure)
- [Data Sources](#data-sources)
- [Troubleshooting](#troubleshooting)

---

## What it does

Every time you hit **▶ Run Analysis**, 11 agents run — most concurrently — and produce a single plain-English recommendation:

- ☀️ How much solar will the 9 kW system generate today and tomorrow?
- 🔋 Should the battery export to the grid, soak solar, or preserve charge?
- ⛽ Is the cheapest P98 pump within 25 km worth riding to, after accounting for the fuel you'll burn getting there?
- 🌐 Is Brent Crude rising or falling — fill up now or wait?
- 🏍️ What's the best 2-hour window to ride the MT-10 today?
- 🚀 What phase is the moon in, and is the ISS passing overhead tonight?
- 🧠 Claude Sonnet synthesises everything into a 3-sentence briefing.

---

## Architecture

```
Browser (HTTPS)
      │
      ▼
CloudFront (d31k8f0371hj3b.cloudfront.net)
      │  redirect-to-https, WebSocket pass-through
      ▼
Application Load Balancer  (port 80)
      │
      ▼
ECS Fargate  (512 vCPU / 1 GB, Streamlit port 8501)
      │  dashboard.py
      ▼
┌─────────────────────────── Orchestrator ──────────────────────────────┐
│                                                                        │
│  Concurrent ─────────────────────────────────────────────────────     │
│  ☀ SolarAnalyst  ⛽ FuelScout  🌐 MacroGeopolitics  🌤 RideScout  🚀 SpaceWatch  │
│                                                                        │
│  Sequential ─────────────────────────────────────────────────────     │
│  SolarAnalyst → BatteryManager → GridArbitrage                        │
│  FuelScout    → Logistics      → MT10Calculator                       │
│  All agents   ──────────────→  ClaudeAdvisor (LLM synthesis)         │
└────────────────────────────────────────────────────────────────────────┘

AWS Bedrock AgentCore (backend API, arm64 container)
  └── Same orchestrator, invoked via CLI or SDK
      └── Logs → CloudWatch /aws/bedrock-agentcore/AustralAgentCore
```

---

## Agents

| Agent | Role | API | Key needed |
|---|---|---|---|
| **SolarAnalyst** | 24 h solar irradiance + kWh yield forecast | Open-Meteo | No |
| **BatteryManager** | GRID_EXPORT / SOLAR_SOAK / PRESERVE strategy | — (logic) | No |
| **GridArbitrage** | NSW NEM spot price → EXPORT / STORE / CONSUME | AEMO public | No |
| **FuelScout** | Cheapest P98 within 25 km, OAuth2 to NSW FuelCheck | NSW FuelCheck | Optional |
| **Logistics** | Riding distance from home to pump | OSRM | No |
| **MT10Calculator** | Is the detour profitable after the fuel cost? | — (math) | No |
| **MacroGeopolitics** | Live Brent Crude + AUD/USD trend sentiment | Yahoo Finance | No |
| **RideScout** | Hourly ride score (0–100) + best window | Open-Meteo | No |
| **SpaceWatch** | ISS position + moon phase + stargazing score | wheretheiss.at | No |
| **ClaudeAdvisor** | LLM synthesis of all agent outputs | Anthropic Claude | **Yes** |

All agents have a synthetic fallback — the dashboard always loads even with no API keys configured.

---

## Local Setup

### 1. Clone

```bash
git clone https://github.com/binzidd/agenttoagent.git
cd agenttoagent
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```ini
# Required for chat + Claude synthesis
ANTHROPIC_API_KEY=sk-ant-...

# Optional — falls back to synthetic data when absent
NSW_FUELCHECK_API_KEY=
NSW_FUELCHECK_API_SECRET=
```

### 4. Run

```bash
cd backend
streamlit run dashboard.py
```

Open **http://localhost:8501**, click **▶ Run Analysis**.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Claude Sonnet API key. [Get one here](https://console.anthropic.com) |
| `NSW_FUELCHECK_API_KEY` | — | NSW FuelCheck key (OAuth2 client ID). [Register free](https://api.nsw.gov.au/Product/Index/22) |
| `NSW_FUELCHECK_API_SECRET` | — | NSW FuelCheck OAuth2 client secret |
| `HOME_LAT` | `-33.93` | Home latitude (Austral NSW) |
| `HOME_LON` | `150.82` | Home longitude |
| `HOME_POSTCODE` | `2179` | Fuel search postcode |
| `SOLAR_SYSTEM_KW` | `9.0` | Installed solar capacity (kW) |
| `BATTERY_CAPACITY_KWH` | `9.0` | Battery capacity (kWh) |
| `FEED_IN_TARIFF_CENTS` | `5.0` | Solar export rate (c/kWh) |
| `BIKE_CONSUMPTION_L_100KM` | `7.5` | MT-10 fuel consumption |
| `BIKE_TANK_FILL_LITRES` | `15.0` | Typical fill volume |

---

## AWS Deployment — Full Walkthrough

This section documents every step taken to deploy this project to AWS, including every gotcha encountered along the way.

### Overview of what gets deployed

| Resource | Purpose | Cost estimate |
|---|---|---|
| ECR — `austral_agentcore` | arm64 container image for the backend | ~$0.10/GB/month |
| ECR — `austral_dashboard` | amd64 container image for Streamlit | ~$0.10/GB/month |
| Bedrock AgentCore runtime | Managed backend agent endpoint | Pay-per-invocation |
| ECS Fargate cluster + service | Runs the Streamlit dashboard | ~$18/month (512 vCPU/1 GB, 24/7) |
| Application Load Balancer | Stable entry point in front of ECS | ~$6/month fixed |
| CloudFront distribution | HTTPS termination, global CDN | ~$0/month at low traffic |
| CloudWatch log group | 14-day trace retention for AgentCore | Negligible |

---

### Prerequisites

- **AWS CLI v2** — [install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Docker Desktop** — running and logged in
- **jq** — `brew install jq`
- **AWS credentials** — configured via `aws configure` (or environment variables)

```bash
aws sts get-caller-identity   # confirm you're authenticated
docker info                   # confirm Docker is running
```

---

### Step 1 — Create the AgentCore IAM execution role

AgentCore needs an IAM role to pull your container from ECR and write logs.

```bash
# Create the role with AgentCore as the trusted service
aws iam create-role \
  --role-name AustralAgentCoreRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"bedrock-agentcore.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

# Attach the managed policy (gives AgentCore full access to itself)
aws iam attach-role-policy \
  --role-name AustralAgentCoreRole \
  --policy-arn arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess

# Allow AgentCore to pull your ECR image
aws iam attach-role-policy \
  --role-name AustralAgentCoreRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

# Allow the container to write logs to CloudWatch
aws iam put-role-policy \
  --role-name AustralAgentCoreRole \
  --policy-name CloudWatchLogs \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],
      "Resource":"arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/*"
    }]
  }'
```

---

### Step 2 — Create the CloudWatch log group

```bash
aws logs create-log-group \
  --log-group-name /aws/bedrock-agentcore/AustralAgentCore \
  --region ap-southeast-2

aws logs put-retention-policy \
  --log-group-name /aws/bedrock-agentcore/AustralAgentCore \
  --retention-in-days 14 \
  --region ap-southeast-2
```

---

### Step 3 — Deploy

The [deploy.sh](./deploy.sh) script handles everything from here.

```bash
# Deploy just the backend to AgentCore:
./deploy.sh agentcore

# Deploy just the Streamlit dashboard to ECS + ALB + CloudFront:
./deploy.sh dashboard

# Deploy both:
./deploy.sh all
```

On first run `deploy.sh` will:
- Create ECR repositories with scan-on-push and a 3-image lifecycle policy
- Build the Docker image and push to ECR
- Create the AgentCore runtime (backend) or ECS service + ALB (dashboard)

> **Note:** `deploy.sh` has the AWS account ID and default VPC/subnet IDs hardcoded for this project's environment. Fork users should update those values at the top of the file.

---

### Gotchas encountered (and fixed)

These are real issues hit during deployment, documented so you don't repeat them.

#### ❶ AgentCore only accepts `arm64` containers

```
ValidationException: Architecture incompatible for uri '...'.
Supported architectures: [arm64]
```

The Dockerfile builds `linux/arm64`. ECS Fargate (dashboard) stays on `linux/amd64`. They use separate ECR repos.

```bash
# AgentCore — arm64
docker build --platform linux/arm64 -f Dockerfile ...

# ECS dashboard — amd64
docker build --platform linux/amd64 -f Dockerfile.streamlit ...
```

#### ❷ AgentCore control plane is `bedrock-agentcore-control`, not `bedrock-agentcore`

`aws bedrock-agentcore` is the **data plane** (invoke, sessions, memory).
`aws bedrock-agentcore-control` is the **control plane** (create/update/list runtimes).

```bash
# ✅ Correct
aws bedrock-agentcore-control create-agent-runtime ...
aws bedrock-agentcore-control list-agent-runtimes ...

# ❌ Wrong — these commands don't exist here
aws bedrock-agentcore create-agent-runtime ...
```

#### ❸ AgentCore runtime names cannot contain hyphens

Pattern constraint: `[a-zA-Z][a-zA-Z0-9_]{0,47}` — underscores only, no hyphens.

```bash
# ✅ Valid
--agent-runtime-name "AustralAgentCore"

# ❌ Invalid — causes ParamValidation
--agent-runtime-name "austral-agentcore"
```

#### ❹ Environment variable JSON must be built with `jq`

If your `.env` file has quoted values (`ANTHROPIC_API_KEY="sk-ant-..."`), inline shell string interpolation into JSON produces double-quoted values and a parse error:

```
Invalid JSON: ... "ANTHROPIC_API_KEY": ""sk-ant-..."" ...
```

Fix: strip quotes from `.env` values, then use `jq --arg` to safely build the JSON object:

```bash
env_val() {
  local raw
  raw=$(grep "^${1}=" backend/.env 2>/dev/null | cut -d= -f2-)
  raw="${raw%\"}" ; raw="${raw#\"}"
  echo "${raw}"
}

build_env_json() {
  jq -n \
    --arg anthropic   "$(env_val ANTHROPIC_API_KEY)" \
    --arg fuel_key    "$(env_val NSW_FUELCHECK_API_KEY)" \
    --arg fuel_secret "$(env_val NSW_FUELCHECK_API_SECRET)" \
    '{ANTHROPIC_API_KEY:$anthropic, NSW_FUELCHECK_API_KEY:$fuel_key, NSW_FUELCHECK_API_SECRET:$fuel_secret}'
}
```

#### ❺ ECS task execution role needs `logs:CreateLogGroup` separately

`AmazonECSTaskExecutionRolePolicy` does not include `logs:CreateLogGroup`. Tasks fail to start with:

```
ResourceInitializationError: failed to validate logger args: ...
AccessDeniedException: not authorized to perform: logs:CreateLogGroup
```

Fix: create the log group manually first, and add the permission:

```bash
aws logs create-log-group --log-group-name /ecs/austral-dashboard --region ap-southeast-2

aws iam put-role-policy \
  --role-name AustralDashboardTaskExecRole \
  --policy-name CloudWatchLogsCreateGroup \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Action":["logs:CreateLogGroup"],
      "Resource":"arn:aws:logs:ap-southeast-2:<account>:log-group:*"
    }]
  }'
```

#### ❻ AWS App Runner requires a subscription (root credentials can't use it)

```
SubscriptionRequiredException: The AWS Access Key Id needs a subscription for the service
```

Solution: use **ECS Fargate** instead of App Runner. Same result, no subscription required.

#### ❼ Security group descriptions must be plain ASCII

```
InvalidParameterValue: Value for parameter GroupDescription is invalid.
Character sets beyond ASCII are not supported.
```

Any em dash (`–`), smart quote, or non-ASCII character in the description causes this. Use plain ASCII only.

#### ❽ ALB idle timeout must be raised for Streamlit WebSocket sessions

The default ALB idle timeout is 60 seconds. Streamlit uses persistent WebSocket connections. Sessions drop silently after 60 seconds of no interaction.

```bash
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn <arn> \
  --attributes Key=idle_timeout.timeout_seconds,Value=3600
```

#### ❾ ECS service cannot have a load balancer added after creation

You cannot call `aws ecs update-service` to add an ALB to an existing service. The service must be deleted and recreated with `--load-balancers` specified at creation time.

```bash
# Scale to 0, then delete
aws ecs update-service --cluster <cluster> --service <name> --desired-count 0
aws ecs delete-service --cluster <cluster> --service <name>
# Wait for DRAINING to complete (~30 s), then recreate
aws ecs create-service ... --load-balancers "..."
```

---

### Invoking the AgentCore backend

```bash
# Full analysis
aws bedrock-agentcore invoke-agent-runtime \
  --region ap-southeast-2 \
  --agent-runtime-id AustralAgentCore-mhgPlO9T4b \
  --payload '{"action":"full_analysis"}' \
  response.json && cat response.json

# Natural language
aws bedrock-agentcore invoke-agent-runtime \
  --region ap-southeast-2 \
  --agent-runtime-id AustralAgentCore-mhgPlO9T4b \
  --payload '{"prompt":"Should I fill up today?"}' \
  response.json && cat response.json
```

Available actions: `full_analysis` · `solar` · `fuel` · `ride` · `grid` · `chat`

---

## Observability — Tracing in CloudWatch

Every agent lifecycle event is logged as a structured JSON line to stdout, captured by the AgentCore runtime and forwarded to:

```
CloudWatch → Log groups → /aws/bedrock-agentcore/AustralAgentCore
```

Example log line:
```json
{
  "ts": "2026-03-25T05:30:12.441Z",
  "level": "INFO",
  "event": "agent_complete",
  "agent": "SolarAnalyst",
  "data": { "forecast_yield_kwh_today": 38.2, "peak_generation_hour": 12 }
}
```

**Tail logs live:**

```bash
aws logs tail /aws/bedrock-agentcore/AustralAgentCore \
  --region ap-southeast-2 \
  --follow \
  --format short
```

**CloudWatch Logs Insights query — see all agent completions for a run:**

```
fields ts, agent, event, data.forecast_yield_kwh_today, data.price, data.score
| filter event in ["agent_complete", "workflow_complete"]
| sort ts asc
```

---

## Project Structure

```
agenttoagent/
├── Dockerfile                     # AgentCore backend — linux/arm64
├── Dockerfile.streamlit           # Dashboard — linux/amd64
├── deploy.sh                      # One-command deploy to AWS
├── README.md
│
└── backend/
    ├── dashboard.py               # Streamlit dashboard (primary UI)
    ├── main.py                    # AgentCore entry point + structured logging
    ├── orchestrator.py            # Concurrent + sequential agent coordination
    ├── api.py                     # FastAPI + WebSocket server (optional)
    ├── config.py                  # Pydantic settings
    ├── requirements.txt
    ├── .env.example
    │
    └── agents/
        ├── solar_analyst.py       # Open-Meteo irradiance forecast
        ├── battery_manager.py     # Charge/export/preserve strategy
        ├── grid_arbitrage.py      # AEMO NEM spot price arbitrage
        ├── fuel_scout.py          # NSW FuelCheck OAuth2 + Haversine filter
        ├── logistics.py           # OSRM open routing
        ├── mt10_calculator.py     # Detour profitability maths
        ├── macro_geopolitics.py   # Brent Crude + AUD/USD via yfinance
        ├── ride_scout.py          # Hourly weather ride scorer
        ├── space_watch.py         # ISS position + moon phase (wheretheiss.at)
        └── claude_advisor.py      # Claude Sonnet synthesis + streaming chat
```

---

## Data Sources

| Data | Provider | Free | Docs |
|---|---|---|---|
| Solar irradiance + weather | Open-Meteo | ✅ | [open-meteo.com](https://open-meteo.com) |
| Riding distance | OSRM | ✅ | [project-osrm.org](http://project-osrm.org) |
| Brent Crude + AUD/USD | Yahoo Finance via yfinance | ✅ | — |
| NEM electricity spot price | AEMO | ✅ | [aemo.com.au](https://aemo.com.au) |
| ISS position | wheretheiss.at | ✅ | [wheretheiss.at](https://wheretheiss.at/w/tracker) |
| P98 fuel prices | NSW FuelCheck | ✅ (key required) | [api.nsw.gov.au](https://api.nsw.gov.au/Product/Index/22) |
| LLM synthesis + chat | Anthropic Claude | Paid | [console.anthropic.com](https://console.anthropic.com) |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'pydantic_settings'`

```bash
pip install pydantic-settings httpx yfinance anthropic plotly streamlit
```

### Chat returns "⚠️ Set ANTHROPIC_API_KEY"

Add to `backend/.env`:
```ini
ANTHROPIC_API_KEY=sk-ant-...
```

### Fuel prices show `(est.)` badge

No FuelCheck key configured — app falls back to synthetic prices. [Register free](https://api.nsw.gov.au/Product/Index/22).

### AgentCore invocation returns immediately with no result

Check that the runtime status is `READY`:

```bash
aws bedrock-agentcore-control list-agent-runtimes --region ap-southeast-2
```

If status is `UPDATING`, wait ~2 minutes after a deploy before invoking.

### Dashboard CloudFront URL returns 503

ECS task may have restarted (new public IP). The ALB health check re-registers it within ~30 seconds. Wait and refresh.
