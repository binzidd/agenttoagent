"""
AustralOrchestrator – coordinates all agents and emits real-time trace events
over the WebSocket connection so the frontend can animate the agent flow graph.

Trace event schema:
{
    "type":      "trace",
    "event":     "agent_start" | "agent_data" | "agent_complete" | "handoff",
    "agent":     "<AgentName>",
    "target":    "<TargetAgentName>" | null,   # set on handoff events
    "data":      { ... },                       # agent output or partial data
    "timestamp": "ISO-8601"
}
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from agents.solar_analyst import SolarAnalyst
from agents.battery_manager import BatteryManager
from agents.claude_advisor import synthesise as claude_synthesise
from agents.fuel_scout import FuelScoutAgent
from agents.logistics import LogisticsAgent
from agents.mt10_calculator import MT10Calculator
from agents.macro_geopolitics import MacroGeopoliticsAgent
from agents.ride_scout import RideScoutAgent
from agents.grid_arbitrage import GridArbitrageAgent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AustralOrchestrator:
    def __init__(self, send_event=None):
        """
        send_event: async callable(dict) – called for each trace event.
        Pass None for non-WS usage (REST endpoints, CLI).
        """
        self._send = send_event

    async def _emit(
        self,
        event: str,
        agent: str,
        data: Any,
        target: Optional[str] = None,
    ):
        if self._send is None:
            return
        await self._send(
            {
                "type": "trace",
                "event": event,
                "agent": agent,
                "target": target,
                "data": data,
                "timestamp": _now(),
            }
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Full workflow
    # ─────────────────────────────────────────────────────────────────────────
    async def run_full_analysis(self) -> dict:
        """
        Runs all agent pipelines concurrently where possible, then
        sequences the dependent fuel-run calculations.
        Returns the complete result dict used by the REST endpoint.
        """
        await self._emit("workflow_start", "Orchestrator", {"message": "Analysis starting…"})

        # ── Concurrent: solar + macro + ride (no dependencies) ──────────────
        await self._emit("agent_start", "SolarAnalyst", {})
        await self._emit("agent_start", "MacroGeopolitics", {})
        await self._emit("agent_start", "RideScout", {})
        await self._emit("agent_start", "FuelScout", {})

        solar_task = asyncio.create_task(SolarAnalyst().get_solar_forecast())
        macro_task = asyncio.create_task(MacroGeopoliticsAgent().get_market_context())
        ride_task = asyncio.create_task(RideScoutAgent().get_ride_window())
        fuel_task = asyncio.create_task(FuelScoutAgent().get_cheapest_p98())

        solar, macro, ride, pumps = await asyncio.gather(
            solar_task, macro_task, ride_task, fuel_task
        )

        await self._emit("agent_complete", "SolarAnalyst", solar)
        await self._emit("agent_complete", "MacroGeopolitics", macro)
        await self._emit("agent_complete", "RideScout", ride)
        await self._emit("agent_complete", "FuelScout", pumps)

        # ── Battery strategy (depends on solar) ─────────────────────────────
        await self._emit("handoff", "SolarAnalyst", solar["forecast_yield_kwh_today"], target="BatteryManager")
        await self._emit("agent_start", "BatteryManager", {})
        battery = await BatteryManager().get_strategy(solar["forecast_yield_kwh_today"])
        await self._emit("agent_complete", "BatteryManager", battery)

        # ── Grid arbitrage (depends on battery fill) ─────────────────────────
        await self._emit("handoff", "BatteryManager", battery["estimated_battery_fill_pct"], target="GridArbitrage")
        await self._emit("agent_start", "GridArbitrage", {})
        grid = await GridArbitrageAgent().get_arbitrage_advice(battery["estimated_battery_fill_pct"])
        await self._emit("agent_complete", "GridArbitrage", grid)

        # ── Fuel run chain ───────────────────────────────────────────────────
        best_pump = min(pumps, key=lambda x: x["price"])
        await self._emit("handoff", "FuelScout", best_pump, target="Logistics")

        await self._emit("agent_start", "Logistics", {})
        route = await LogisticsAgent().get_route(best_pump["lat"], best_pump["lon"])
        await self._emit("agent_complete", "Logistics", route)

        await self._emit("handoff", "Logistics", route["round_trip_km"], target="MT10Calculator")
        await self._emit("agent_start", "MT10Calculator", {})

        # Use the most expensive local pump price as the local reference
        local_price = max(pumps, key=lambda x: x["price"])["price"]
        decision = await MT10Calculator().is_detour_worth_it(
            distance_km=route["distance_km"],
            local_price=local_price,
            target_price=best_pump["price"],
        )
        await self._emit("agent_complete", "MT10Calculator", decision)

        result = {
            "solar": solar,
            "battery": battery,
            "grid": grid,
            "fuel_pumps": pumps,
            "best_pump": best_pump,
            "route": route,
            "decision": decision,
            "macro": macro,
            "ride": ride,
        }

        # ── ClaudeAdvisor: LLM synthesis of all agent outputs ────────────────
        await self._emit("agent_start", "ClaudeAdvisor", {})
        summary = await claude_synthesise(result)
        await self._emit("agent_complete", "ClaudeAdvisor", {"summary": summary})

        await self._emit(
            "workflow_complete",
            "Orchestrator",
            {"decision": "GO" if decision["profitable"] else "STAY", "summary": summary},
        )

        result["summary"] = summary
        return result
