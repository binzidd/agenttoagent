"""
AWS Bedrock AgentCore Entry Point
==================================
This file is the container entry point when deployed to AWS AgentCore.

Local testing (without AgentCore):
    python main.py

AgentCore payload schema:
    {
        "action":   "full_analysis" | "chat" | "solar" | "fuel" | "ride" | "grid",
        "prompt":   "Optional natural language prompt",
        "messages": [{"role": "user", "content": "..."}],   # for action=chat
        "context":  { ...AnalysisResult }                   # for action=chat
    }

AgentCore response schema:
    {
        "status":  "SUCCESS" | "ERROR",
        "action":  "<action>",
        "result":  { ... },
        "summary": "Plain text summary (action=full_analysis only)"
    }

Logs (stdout → CloudWatch /aws/bedrock-agentcore/AustralAgentCore):
    Every agent start / complete / handoff emits a JSON line:
    {"ts":"...","level":"INFO","event":"agent_complete","agent":"SolarAnalyst","data":{...}}
"""

from __future__ import annotations
import asyncio
import json
import logging
import sys
import os
from datetime import datetime, timezone

# Ensure local modules are importable when run inside a container
sys.path.insert(0, os.path.dirname(__file__))

# ─── Logging setup ────────────────────────────────────────────────────────────
# Structured JSON to stdout so CloudWatch Logs Insights can query fields.

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via logger.info(..., extra={...})
        for key in ("event", "agent", "target", "data"):
            if hasattr(record, key):
                doc[key] = getattr(record, key)
        return json.dumps(doc, default=str)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("agentcore")

# ─── AgentCore SDK ────────────────────────────────────────────────────────────
try:
    from bedrock_agentcore import BedrockAgentCoreApp
    _AGENTCORE_AVAILABLE = True
except ImportError:
    _AGENTCORE_AVAILABLE = False
    BedrockAgentCoreApp = None

from orchestrator import AustralOrchestrator
from agents.solar_analyst import SolarAnalyst
from agents.fuel_scout import FuelScoutAgent
from agents.ride_scout import RideScoutAgent
from agents.grid_arbitrage import GridArbitrageAgent
from agents.claude_advisor import stream_chat


# ─── Trace emitter ────────────────────────────────────────────────────────────

async def _emit_trace(event: dict) -> None:
    """
    Passed as send_event to AustralOrchestrator.
    Each agent lifecycle event becomes a structured log line visible in
    CloudWatch Logs under /aws/bedrock-agentcore/AustralAgentCore.
    """
    log.info(
        "%s › %s",
        event.get("agent", "?"),
        event.get("event", "?"),
        extra={
            "event":  event.get("event"),
            "agent":  event.get("agent"),
            "target": event.get("target"),
            "data":   event.get("data"),
        },
    )


# ─── Handlers ────────────────────────────────────────────────────────────────

async def handle_full_analysis() -> dict:
    log.info("invoke › full_analysis started")
    orchestrator = AustralOrchestrator(send_event=_emit_trace)
    result = await orchestrator.run_full_analysis()
    log.info("invoke › full_analysis complete", extra={"data": {"decision": result.get("decision", {}).get("profitable")}})
    return {
        "status":  "SUCCESS",
        "action":  "full_analysis",
        "result":  result,
        "summary": result.get("summary", ""),
    }


async def handle_chat(messages: list, context: dict | None) -> dict:
    log.info("invoke › chat (%d messages)", len(messages))
    parts: list[str] = []
    async for chunk in stream_chat(messages, context):
        parts.append(chunk)
    return {"status": "SUCCESS", "action": "chat", "response": "".join(parts)}


async def handle_solar() -> dict:
    data = await SolarAnalyst().get_solar_forecast()
    return {"status": "SUCCESS", "action": "solar", "result": data}


async def handle_fuel() -> dict:
    data = await FuelScoutAgent().get_cheapest_p98()
    return {"status": "SUCCESS", "action": "fuel", "result": data}


async def handle_ride() -> dict:
    data = await RideScoutAgent().get_ride_window()
    return {"status": "SUCCESS", "action": "ride", "result": data}


async def handle_grid() -> dict:
    data = await GridArbitrageAgent().get_arbitrage_advice()
    return {"status": "SUCCESS", "action": "grid", "result": data}


# ─── Router ──────────────────────────────────────────────────────────────────

async def invoke(payload: dict) -> dict:
    action = payload.get("action") or "full_analysis"
    if "prompt" in payload and "action" not in payload:
        action = "full_analysis"

    log.info("invoke › action=%s", action)
    try:
        if action == "full_analysis":
            return await handle_full_analysis()
        elif action == "chat":
            return await handle_chat(
                messages=payload.get("messages", []),
                context=payload.get("context"),
            )
        elif action == "solar":
            return await handle_solar()
        elif action == "fuel":
            return await handle_fuel()
        elif action == "ride":
            return await handle_ride()
        elif action == "grid":
            return await handle_grid()
        else:
            return {"status": "ERROR", "message": f"Unknown action: {action}"}
    except Exception as exc:
        log.exception("invoke › unhandled error for action=%s", action)
        return {"status": "ERROR", "action": action, "message": str(exc)}


# ─── Bootstrap ───────────────────────────────────────────────────────────────

if _AGENTCORE_AVAILABLE:
    app = BedrockAgentCoreApp()

    @app.entrypoint
    async def agentcore_handler(payload: dict) -> dict:
        return await invoke(payload)

    if __name__ == "__main__":
        app.run()

else:
    if __name__ == "__main__":
        test_payload = {"action": "full_analysis"}
        log.info("local test invocation – no AgentCore SDK")
        result = asyncio.run(invoke(test_payload))
        print(json.dumps(result, indent=2, default=str))
