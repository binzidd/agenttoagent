"""
ClaudeAdvisor – the reasoning brain of the stack.

Takes the structured outputs from all other agents and asks Claude to produce
a plain-English synthesis: what does it all mean, and what should the user do?

This is what was missing in v1 — the agents collected data but nothing
reasoned over it with language understanding.
"""
import json
import anthropic
from config import settings

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are the personal AI advisor for a household in Austral, NSW, Australia.
The user has a 9 kW rooftop solar system, a 9 kWh SolarEdge Nexis home battery,
and a Yamaha MT-10 motorcycle that runs on Premium 98 fuel.

You receive structured JSON data from a set of specialised agents that monitor:
- Solar forecast and battery strategy
- Live P98 fuel prices and whether a detour to a cheaper pump is profitable
- Brent Crude oil prices and AUD/USD exchange rate
- Today's riding weather score (0-100) and best ride window
- NSW electricity spot price and whether to export solar or store it

Respond conversationally and helpfully. Be concise (2-4 sentences unless more detail is asked for).
Always ground your answer in the actual data provided. If a value is missing or unavailable, say so.
When asked for a recommendation, give a clear YES/NO/WAIT answer first, then explain briefly."""


def _build_context(analysis: dict) -> str:
    """Convert the analysis result dict into a compact context block for Claude."""
    solar = analysis.get("solar", {})
    battery = analysis.get("battery", {})
    grid = analysis.get("grid", {})
    best_pump = analysis.get("best_pump", {})
    decision = analysis.get("decision", {})
    macro = analysis.get("macro", {})
    ride = analysis.get("ride", {})
    route = analysis.get("route", {})

    return f"""
=== CURRENT AGENT DATA ===

SOLAR:
- Today's forecast yield: {solar.get('forecast_yield_kwh_today')} kWh
- Tomorrow's forecast: {solar.get('forecast_yield_kwh_tomorrow')} kWh
- Peak generation hour: {solar.get('peak_generation_hour')}:00
- Status: {solar.get('status')}
- Avg cloud cover: {solar.get('avg_cloud_cover_pct')}%

BATTERY:
- Strategy mode: {battery.get('mode')}
- Estimated fill: {battery.get('estimated_battery_fill_pct')}%
- Excess solar: {battery.get('excess_solar_kwh')} kWh
- Detail: {battery.get('detail')}

GRID ARBITRAGE:
- NSW NEM spot price: {grid.get('nem_spot_cents_kwh')} c/kWh
- Feed-in tariff: {grid.get('feed_in_tariff_cents')} c/kWh
- Recommendation: {grid.get('recommended_action')}
- Reason: {grid.get('reason')}

FUEL:
- Cheapest P98: {best_pump.get('name')} at ${best_pump.get('price')}/L
- Distance: {route.get('distance_km')} km one-way
- Net profit from detour: ${decision.get('net_profit')}
- Decision: {"GO - profitable" if decision.get('profitable') else "STAY - not worth it"}
- Logic: {decision.get('logic')}

MACRO / OIL MARKETS:
- Brent Crude: ${macro.get('brent_crude_usd')} ({macro.get('brent_change_pct'):+.2f}% today)
- AUD/USD: {macro.get('aud_usd')}
- Trend: {macro.get('crude_trend')}
- Macro recommendation: {macro.get('recommendation')}

RIDE CONDITIONS:
- Day score: {ride.get('overall_day_score')}/100
- Best window: {ride.get('best_window_start')}:00 – {(ride.get('best_window_start') or 0) + 2}:00
- Recommendation: {ride.get('recommendation')}
""".strip()


async def synthesise(analysis: dict) -> str:
    """
    Non-streaming: ask Claude for a one-paragraph executive summary
    of all agent outputs. Called at end of workflow run.
    """
    if not settings.anthropic_api_key:
        return _fallback_summary(analysis)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    context = _build_context(analysis)

    message = await client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    "Give me a 2-3 sentence executive summary of what today looks like "
                    "across solar, fuel, riding, and the grid."
                ),
            }
        ],
    )
    return message.content[0].text


async def stream_chat(messages: list[dict], analysis: dict | None):
    """
    Streaming generator for the chat endpoint.
    Yields text chunks as they arrive from Claude.
    """
    if not settings.anthropic_api_key:
        yield "⚠️ No ANTHROPIC_API_KEY set. Add it to backend/.env to enable chat."
        return

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = SYSTEM_PROMPT
    if analysis:
        system += f"\n\n{_build_context(analysis)}"

    async with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


def _fallback_summary(analysis: dict) -> str:
    """Plain-text summary when no API key is configured."""
    decision = analysis.get("decision", {})
    ride = analysis.get("ride", {})
    solar = analysis.get("solar", {})
    grid = analysis.get("grid", {})

    parts = []
    parts.append(
        f"Solar forecast: {solar.get('forecast_yield_kwh_today')} kWh today "
        f"({solar.get('status')} output), battery strategy is {analysis.get('battery', {}).get('mode')}."
    )
    parts.append(
        f"Fuel run: {'GO' if decision.get('profitable') else 'STAY'} — "
        f"{decision.get('logic', '')}"
    )
    parts.append(f"Grid: {grid.get('recommended_action')} — {grid.get('reason', '')}")
    parts.append(f"Riding: {ride.get('recommendation', '')}")
    return " ".join(parts)
