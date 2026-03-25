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
"""

from __future__ import annotations
import asyncio
import sys
import os

# Ensure local modules are importable when run inside a container
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Attempt to import the real AgentCore SDK (available inside container)
    from bedrock_agentcore import BedrockAgentCoreApp
    _AGENTCORE_AVAILABLE = True
except ImportError:
    # Graceful fallback for local testing without the SDK
    _AGENTCORE_AVAILABLE = False
    BedrockAgentCoreApp = None

from orchestrator import AustralOrchestrator
from agents.solar_analyst import SolarAnalyst
from agents.fuel_scout import FuelScoutAgent
from agents.ride_scout import RideScoutAgent
from agents.grid_arbitrage import GridArbitrageAgent
from agents.claude_advisor import stream_chat


# ─── Handlers ────────────────────────────────────────────────────────────────

async def handle_full_analysis() -> dict:
    orchestrator = AustralOrchestrator(send_event=None)
    result = await orchestrator.run_full_analysis()
    return {
        "status": "SUCCESS",
        "action": "full_analysis",
        "result": result,
        "summary": result.get("summary", ""),
    }


async def handle_chat(messages: list, context: dict | None) -> dict:
    response_parts = []
    async for chunk in stream_chat(messages, context):
        response_parts.append(chunk)
    return {
        "status": "SUCCESS",
        "action": "chat",
        "response": "".join(response_parts),
    }


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


# ─── AgentCore Entry Point ───────────────────────────────────────────────────

async def invoke(payload: dict) -> dict:
    """
    Main handler – called by AgentCore for every invocation.

    Supports both:
      - Structured: {"action": "full_analysis"}
      - Natural language: {"prompt": "Should I fill up today?"}
        (routes to full_analysis + Claude summary)
    """
    action = payload.get("action") or "full_analysis"

    # Allow natural-language prompts to map to full_analysis
    if "prompt" in payload and "action" not in payload:
        action = "full_analysis"

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
        return {"status": "ERROR", "action": action, "message": str(exc)}


# ─── Bootstrap ───────────────────────────────────────────────────────────────

if _AGENTCORE_AVAILABLE:
    # Production path: wrap with BedrockAgentCoreApp
    app = BedrockAgentCoreApp()

    @app.entrypoint
    async def agentcore_handler(payload: dict) -> dict:
        return await invoke(payload)

    if __name__ == "__main__":
        app.run()

else:
    # Local testing path: run a single test invocation
    if __name__ == "__main__":
        import json

        test_payload = {"action": "full_analysis"}
        print("Running local test invocation…")
        result = asyncio.run(invoke(test_payload))
        print(json.dumps(result, indent=2, default=str))
