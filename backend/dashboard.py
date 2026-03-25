"""
Austral Agent Stack – Streamlit Dashboard
Run: cd backend && streamlit run dashboard.py
"""

import sys, os, asyncio, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from anthropic import Anthropic

from config import settings
from agents.solar_analyst import SolarAnalyst
from agents.battery_manager import BatteryManager
from agents.grid_arbitrage import GridArbitrageAgent
from agents.fuel_scout import FuelScoutAgent
from agents.logistics import LogisticsAgent
from agents.mt10_calculator import MT10Calculator
from agents.macro_geopolitics import MacroGeopoliticsAgent
from agents.ride_scout import RideScoutAgent
from agents.claude_advisor import _build_context, SYSTEM_PROMPT

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Austral Agent Stack",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Remove default padding */
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1400px; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 1rem 1.25rem;
}
[data-testid="metric-container"] label { color: #64748b; font-size: 0.75rem; }
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f1f5f9;
    font-size: 1.5rem;
    font-weight: 700;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 0.4rem 1rem;
    font-size: 0.85rem;
}

/* Decision banner */
.decision-go {
    background: linear-gradient(135deg, #052e16 0%, #14532d 100%);
    border: 1px solid #16a34a;
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
}
.decision-stay {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
}

/* Chat messages */
.chat-user {
    background: #166534;
    border-radius: 12px 12px 2px 12px;
    padding: 0.6rem 1rem;
    margin: 0.25rem 0;
    margin-left: 20%;
    font-size: 0.9rem;
}
.chat-bot {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px 12px 12px 2px;
    padding: 0.6rem 1rem;
    margin: 0.25rem 0;
    margin-right: 20%;
    font-size: 0.9rem;
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Agent status pills */
.agent-running { color: #facc15; }
.agent-done    { color: #4ade80; }
.agent-idle    { color: #475569; }
</style>
""", unsafe_allow_html=True)

# ─── Session State ────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None
if "traces" not in st.session_state:
    st.session_state.traces = []
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content":
            "Hi! I'm your Austral home advisor. Run the analysis then ask me anything — "
            "solar yield, fuel detour value, ride conditions, grid export timing, you name it."}
    ]


# ─── Analysis Runner ─────────────────────────────────────────────────────────

def run_analysis():
    """Execute all agents sequentially with live Streamlit status updates."""
    traces = []
    result = {}

    with st.status("🚀 **Activating agent crew…**", expanded=True) as status:

        log_placeholder = st.empty()
        log_lines = []

        def log(emoji, agent, msg):
            log_lines.append(f"{emoji} **{agent}**: {msg}")
            log_placeholder.markdown("\n\n".join(log_lines[-8:]))

        def run(coro):
            return asyncio.run(coro)

        # ── Concurrent group ─────────────────────────────────────────────
        log("⚡", "Orchestrator", "dispatching concurrent agents")

        log("☀️", "SolarAnalyst", "fetching Open-Meteo irradiance…")
        solar = run(SolarAnalyst().get_solar_forecast())
        log("☀️", "SolarAnalyst", f"✓ {solar['forecast_yield_kwh_today']} kWh today")
        traces.append({"agent": "SolarAnalyst", "event": "agent_complete", "data": solar})

        log("⛽", "FuelScout", "checking NSW P98 prices…")
        pumps = run(FuelScoutAgent().get_cheapest_p98())
        best_pump = min(pumps, key=lambda x: x["price"])
        log("⛽", "FuelScout", f"✓ cheapest: {best_pump['name']} @ ${best_pump['price']:.3f}/L")
        traces.append({"agent": "FuelScout", "event": "agent_complete", "data": pumps})

        log("🌐", "MacroGeopolitics", "fetching Brent Crude & AUD/USD…")
        macro = run(MacroGeopoliticsAgent().get_market_context())
        log("🌐", "MacroGeopolitics", f"✓ Brent ${macro['brent_crude_usd']} ({macro['crude_trend']})")
        traces.append({"agent": "MacroGeopolitics", "event": "agent_complete", "data": macro})

        log("🌤️", "RideScout", "analysing today's weather window…")
        ride = run(RideScoutAgent().get_ride_window())
        log("🌤️", "RideScout", f"✓ day score {ride['overall_day_score']:.0f}/100")
        traces.append({"agent": "RideScout", "event": "agent_complete", "data": ride})

        # ── Solar chain ───────────────────────────────────────────────────
        log("🔋", "BatteryManager", "calculating storage strategy…")
        battery = run(BatteryManager().get_strategy(solar["forecast_yield_kwh_today"]))
        log("🔋", "BatteryManager", f"✓ mode: {battery['mode']}, fill: {battery['estimated_battery_fill_pct']:.0f}%")
        traces.append({"agent": "BatteryManager", "event": "agent_complete", "data": battery})

        log("⚡", "GridArbitrage", "fetching NEM spot price…")
        grid = run(GridArbitrageAgent().get_arbitrage_advice(battery["estimated_battery_fill_pct"]))
        log("⚡", "GridArbitrage", f"✓ {grid['nem_spot_cents_kwh']:.1f} c/kWh → {grid['recommended_action']}")
        traces.append({"agent": "GridArbitrage", "event": "agent_complete", "data": grid})

        # ── Fuel chain ────────────────────────────────────────────────────
        log("🗺️", "Logistics", f"routing to {best_pump['name']}…")
        route = run(LogisticsAgent().get_route(best_pump["lat"], best_pump["lon"]))
        log("🗺️", "Logistics", f"✓ {route['distance_km']} km one-way, {route['duration_min']:.0f} min")
        traces.append({"agent": "Logistics", "event": "agent_complete", "data": route})

        local_price = max(pumps, key=lambda x: x["price"])["price"]
        log("🏍️", "MT10Calculator", "computing detour profitability…")
        decision = run(MT10Calculator().is_detour_worth_it(
            distance_km=route["distance_km"],
            local_price=local_price,
            target_price=best_pump["price"],
        ))
        log("🏍️", "MT10Calculator", f"✓ net {'+' if decision['net_profit'] >= 0 else ''}${decision['net_profit']:.2f} → {'GO' if decision['profitable'] else 'STAY'}")
        traces.append({"agent": "MT10Calculator", "event": "agent_complete", "data": decision})

        # ── Claude synthesis ───────────────────────────────────────────────
        log("🧠", "ClaudeAdvisor", "synthesising with Claude…")
        full = dict(solar=solar, battery=battery, grid=grid,
                    fuel_pumps=pumps, best_pump=best_pump,
                    route=route, decision=decision, macro=macro, ride=ride)
        if settings.anthropic_api_key:
            client = Anthropic(api_key=settings.anthropic_api_key)
            ctx = _build_context(full)
            msg = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content":
                    f"{ctx}\n\nGive me a 2–3 sentence executive summary of today across solar, fuel, riding, and the grid."}],
            )
            summary = msg.content[0].text
        else:
            summary = (
                f"Solar forecast {solar['forecast_yield_kwh_today']} kWh ({solar['status']}). "
                f"Fuel: {'GO to ' + best_pump['name'] if decision['profitable'] else 'STAY — not profitable'}. "
                f"Ride score {ride['overall_day_score']:.0f}/100. Grid: {grid['recommended_action']}."
            )
        log("🧠", "ClaudeAdvisor", "✓ summary ready")
        full["summary"] = summary
        traces.append({"agent": "ClaudeAdvisor", "event": "agent_complete", "data": {"summary": summary}})

        status.update(label="✅ **Analysis complete!**", state="complete", expanded=False)

    return full, traces


# ─── Plotly Helpers ───────────────────────────────────────────────────────────

TRANSPARENT = "rgba(0,0,0,0)"
GRID_COLOR  = "#1e293b"
TEXT_COLOR  = "#94a3b8"
GREEN       = "#22c55e"
YELLOW      = "#eab308"
RED         = "#ef4444"
BLUE        = "#3b82f6"

def base_layout(title="", height=300):
    return dict(
        title=dict(text=title, font=dict(color="#e2e8f0", size=14), x=0.01),
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor="#0a1628",
        font=dict(color=TEXT_COLOR, size=11),
        margin=dict(l=12, r=12, t=36, b=12),
        height=height,
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showgrid=True),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, showgrid=True),
    )


def solar_chart(solar):
    hours = list(range(24))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=solar["hourly_radiation"],
        fill="tozeroy", fillcolor="rgba(234,179,8,0.15)",
        line=dict(color=YELLOW, width=2),
        name="W/m²",
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=solar["hourly_cloud"],
        line=dict(color="#64748b", width=1, dash="dot"),
        name="Cloud %",
        yaxis="y2",
    ))
    fig.update_layout(
        **base_layout("☀️ Solar Irradiance & Cloud Cover", height=280),
        yaxis2=dict(overlaying="y", side="right", gridcolor=GRID_COLOR,
                    title=dict(text="Cloud %", font=dict(color=TEXT_COLOR)), range=[0, 100]),
        showlegend=True,
        legend=dict(orientation="h", y=1.15, x=0, font=dict(color=TEXT_COLOR)),
        xaxis=dict(tickmode="array", tickvals=list(range(0, 24, 3)),
                   ticktext=[f"{h}:00" for h in range(0, 24, 3)],
                   gridcolor=GRID_COLOR),
    )
    return fig


def fuel_chart(pumps, best_pump):
    sorted_pumps = sorted(pumps, key=lambda x: x["price"])
    colors = [GREEN if p["name"] == best_pump["name"] else "#334155" for p in sorted_pumps]
    names = [p["name"].split()[:2] for p in sorted_pumps]
    short_names = [" ".join(n) for n in names]
    fig = go.Figure(go.Bar(
        x=[p["price"] for p in sorted_pumps],
        y=short_names,
        orientation="h",
        marker_color=colors,
        text=[f"${p['price']:.3f}" for p in sorted_pumps],
        textposition="outside",
        textfont=dict(color=TEXT_COLOR),
    ))
    fig.update_layout(
        **base_layout("⛽ P98 Price Comparison ($/L)", height=240),
        xaxis=dict(range=[min(p["price"] for p in pumps) - 0.05,
                          max(p["price"] for p in pumps) + 0.08],
                   gridcolor=GRID_COLOR),
    )
    return fig


def ride_chart(ride):
    valid = [h for h in ride["hourly_scores"] if h.get("score", 0) > 0 and 6 <= h["hour"] <= 21]
    if not valid:
        return None
    colors = [GREEN if h["score"] >= 70 else YELLOW if h["score"] >= 45 else RED for h in valid]
    fig = go.Figure(go.Bar(
        x=[f"{h['hour']}:00" for h in valid],
        y=[h["score"] for h in valid],
        marker_color=colors,
        text=[f"{h['score']:.0f}" for h in valid],
        textposition="outside",
        textfont=dict(color=TEXT_COLOR, size=10),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Score: %{y:.0f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        **base_layout("🏍️ Hourly Ride Score", height=240),
        yaxis=dict(range=[0, 110], gridcolor=GRID_COLOR),
    )
    return fig


def battery_gauge(pct):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number=dict(suffix="%", font=dict(color="#e2e8f0", size=28)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=TEXT_COLOR,
                      tickfont=dict(color=TEXT_COLOR)),
            bar=dict(color=GREEN),
            bgcolor="#0a1628",
            bordercolor=GRID_COLOR,
            steps=[
                dict(range=[0, 30],  color="#1e293b"),
                dict(range=[30, 70], color="#162032"),
                dict(range=[70, 100], color="#0d2b1a"),
            ],
            threshold=dict(line=dict(color=GREEN, width=3), value=80),
        ),
        title=dict(text="Battery Fill", font=dict(color=TEXT_COLOR, size=13)),
    ))
    fig.update_layout(paper_bgcolor=TRANSPARENT, height=200,
                      margin=dict(l=20, r=20, t=30, b=10))
    return fig


def agent_flow_graph(agent_states: dict):
    """Plotly network graph of all agents coloured by status."""

    nodes = {
        "Orchestrator":     (0.50, 0.55),
        "RideScout":        (0.50, 1.00),
        "SolarAnalyst":     (0.05, 0.85),
        "BatteryManager":   (0.05, 0.55),
        "GridArbitrage":    (0.05, 0.25),
        "FuelScout":        (0.95, 0.85),
        "Logistics":        (0.95, 0.55),
        "MT10Calculator":   (0.95, 0.25),
        "MacroGeopolitics": (0.50, 0.10),
        "ClaudeAdvisor":    (0.50, 0.25),
    }
    edges = [
        ("Orchestrator", "SolarAnalyst"),
        ("Orchestrator", "FuelScout"),
        ("Orchestrator", "MacroGeopolitics"),
        ("Orchestrator", "RideScout"),
        ("SolarAnalyst",  "BatteryManager"),
        ("BatteryManager","GridArbitrage"),
        ("FuelScout",     "Logistics"),
        ("Logistics",     "MT10Calculator"),
        ("Orchestrator",  "ClaudeAdvisor"),
    ]
    emojis = {
        "Orchestrator": "🎯", "SolarAnalyst": "☀️", "BatteryManager": "🔋",
        "GridArbitrage": "⚡", "FuelScout": "⛽", "Logistics": "🗺️",
        "MT10Calculator": "🏍️", "MacroGeopolitics": "🌐", "RideScout": "🌤️",
        "ClaudeAdvisor": "🧠",
    }

    def node_color(name):
        s = agent_states.get(name, "idle")
        return {"running": "#854d0e", "done": "#14532d", "idle": "#1e293b"}.get(s, "#1e293b")

    def border_color(name):
        s = agent_states.get(name, "idle")
        return {"running": YELLOW, "done": GREEN, "idle": "#334155"}.get(s, "#334155")

    fig = go.Figure()

    # Edges
    for src, dst in edges:
        x0, y0 = nodes[src]
        x1, y1 = nodes[dst]
        is_active = (agent_states.get(dst) == "done" or agent_states.get(src) == "done")
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color=GREEN if is_active else "#1e293b", width=2 if is_active else 1),
            hoverinfo="none",
            showlegend=False,
        ))

    # Nodes
    for name, (x, y) in nodes.items():
        status = agent_states.get(name, "idle")
        short = name.replace("Calculator", "Calc").replace("Geopolitics", "& FX")
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers+text",
            marker=dict(
                size=52,
                color=node_color(name),
                line=dict(color=border_color(name), width=2),
                symbol="circle",
            ),
            text=[f"{emojis.get(name, '•')}<br><span style='font-size:9px'>{short}</span>"],
            textfont=dict(color="#e2e8f0", size=11),
            textposition="middle center",
            hovertemplate=f"<b>{name}</b><br>Status: {status}<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor="#060d1a",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.1, 1.1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.05, 1.1]),
    )
    return fig


def macro_gauge(brent, change_pct, trend):
    color = RED if trend == "RISING" else GREEN if trend == "FALLING" else YELLOW
    fig = go.Figure(go.Indicator(
        mode="number+delta",
        value=brent,
        number=dict(prefix="$", suffix=" USD", font=dict(color="#e2e8f0", size=28)),
        delta=dict(reference=brent - brent * change_pct / 100,
                   valueformat=".2f",
                   increasing=dict(color=RED),
                   decreasing=dict(color=GREEN)),
        title=dict(text="Brent Crude", font=dict(color=TEXT_COLOR, size=13)),
    ))
    fig.update_layout(paper_bgcolor=TRANSPARENT, height=160,
                      margin=dict(l=10, r=10, t=40, b=10))
    return fig


# ─── Chat Helper ─────────────────────────────────────────────────────────────

def stream_chat(messages, context):
    if not settings.anthropic_api_key:
        yield "⚠️ Set ANTHROPIC_API_KEY in backend/.env to enable chat."
        return
    client = Anthropic(api_key=settings.anthropic_api_key)
    system = SYSTEM_PROMPT
    if context:
        system += "\n\n" + _build_context(context)
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": m["role"], "content": m["content"]} for m in messages],
    ) as stream:
        yield from stream.text_stream


# ─── Header ──────────────────────────────────────────────────────────────────

col_title, col_btn = st.columns([3, 1])
with col_title:
    st.markdown("## 🏡 Austral Agent Stack")
    st.caption("Multi-agent cost optimisation · Austral NSW · Solar • Fuel • Ride • Grid")

with col_btn:
    st.write("")
    run_clicked = st.button("▶ Run Analysis", type="primary", use_container_width=True)

if run_clicked:
    result, traces = run_analysis()
    st.session_state.result = result
    st.session_state.traces = traces
    # Auto-inject Claude summary into chat
    if result.get("summary"):
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": result["summary"]}
        )
    st.rerun()

st.divider()

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_overview, tab_solar, tab_fuel, tab_ride, tab_flow, tab_chat, tab_trace = st.tabs([
    "🏠 Overview",
    "☀️ Solar & Grid",
    "⛽ Fuel Run",
    "🏍️ Riding",
    "🤖 Agent Flow",
    "💬 Chat",
    "📋 Trace",
])

r = st.session_state.result  # shorthand

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    if r is None:
        st.info("Press **▶ Run Analysis** to fetch live data from all agents.", icon="ℹ️")
    else:
        # ── Decision Banner ────────────────────────────────────────────────
        go_ride = r["decision"]["profitable"]
        banner_class = "decision-go" if go_ride else "decision-stay"
        icon = "🟢" if go_ride else "🔴"
        title_text = f"GO — Head to {r['best_pump']['name']}" if go_ride else "STAY — Not worth the ride"
        st.markdown(f"""
        <div class="{banner_class}">
            <div style="display:flex; align-items:center; gap:1rem; flex-wrap:wrap;">
                <span style="font-size:2.5rem">{icon}</span>
                <div>
                    <div style="font-size:1.4rem; font-weight:700; color:#f1f5f9">{title_text}</div>
                    <div style="color:#94a3b8; margin-top:0.25rem">{r['decision']['logic']}</div>
                </div>
                {"<div style='margin-left:auto;text-align:right'><div style='color:#64748b;font-size:0.75rem'>NET SAVING</div><div style='font-size:2rem;font-weight:800;color:#4ade80'>+$" + f"{r['decision']['net_profit']:.2f}</div></div>" if go_ride else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        # ── Claude Summary ────────────────────────────────────────────────
        if r.get("summary"):
            st.info(r["summary"], icon="🧠")

        # ── Key Metrics ──────────────────────────────────────────────────
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("☀️ Solar Today",    f"{r['solar']['forecast_yield_kwh_today']} kWh",
                  delta=f"Peak {r['solar']['peak_generation_hour']}:00")
        m2.metric("🔋 Battery Fill",   f"{r['battery']['estimated_battery_fill_pct']:.0f}%",
                  delta=r['battery']['mode'].replace('_', ' '))
        m3.metric("⛽ Best P98 Price", f"${r['best_pump']['price']:.3f}/L",
                  delta=r['best_pump']['name'].split()[0])
        m4.metric("🏍️ Ride Score",     f"{r['ride']['overall_day_score']:.0f}/100",
                  delta=f"Best {r['ride']['best_window_start']}:00" if r['ride']['best_window_start'] else "")
        m5.metric("⚡ NEM Spot",       f"{r['grid']['nem_spot_cents_kwh']:.1f} c/kWh",
                  delta=r['grid']['recommended_action'])
        m6.metric("🌐 Brent Crude",    f"${r['macro']['brent_crude_usd']:.1f}",
                  delta=f"{r['macro']['brent_change_pct']:+.1f}%",
                  delta_color="inverse")

        st.write("")

        # ── Mini charts row ───────────────────────────────────────────────
        col_s, col_f = st.columns(2)
        with col_s:
            st.plotly_chart(solar_chart(r["solar"]), use_container_width=True, config={"displayModeBar": False})
        with col_f:
            st.plotly_chart(fuel_chart(r["fuel_pumps"], r["best_pump"]),
                            use_container_width=True, config={"displayModeBar": False})

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: SOLAR & GRID
# ═══════════════════════════════════════════════════════════════════════════════
with tab_solar:
    if r is None:
        st.info("Run analysis first.", icon="ℹ️")
    else:
        col_a, col_b = st.columns([2, 1])

        with col_a:
            st.plotly_chart(solar_chart(r["solar"]), use_container_width=True,
                            config={"displayModeBar": False})

            # Solar details table
            s = r["solar"]
            st.markdown("#### Solar Stats")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Today",    f"{s['forecast_yield_kwh_today']} kWh")
            d2.metric("Tomorrow", f"{s['forecast_yield_kwh_tomorrow']} kWh")
            d3.metric("Peak",     f"{s['peak_generation_hour']}:00")
            d4.metric("Cloud",    f"{s['avg_cloud_cover_pct']}%")

        with col_b:
            st.markdown("#### Battery Strategy")
            st.plotly_chart(battery_gauge(r["battery"]["estimated_battery_fill_pct"]),
                            use_container_width=True, config={"displayModeBar": False})

            bat = r["battery"]
            mode_color = {"GRID_EXPORT": "green", "SOLAR_SOAK": "orange", "PRESERVE": "blue"}
            st.markdown(f"**Mode:** :{mode_color.get(bat['mode'], 'gray')}[{bat['mode'].replace('_',' ')}]")
            st.caption(bat["detail"])

            st.write("")
            st.markdown("#### ⚡ Grid Arbitrage")
            g = r["grid"]
            action_icon = {"EXPORT": "⬆️", "STORE": "🔋", "CONSUME": "⚡"}.get(g["recommended_action"], "")
            st.markdown(f"### {action_icon} {g['recommended_action']}")
            st.caption(g["reason"])

            gc1, gc2 = st.columns(2)
            gc1.metric("NEM Spot", f"{g['nem_spot_cents_kwh']:.1f} c/kWh")
            gc2.metric("Feed-in",  f"{g['feed_in_tariff_cents']:.1f} c/kWh")
            st.caption(f"Source: {'AEMO live' if g['data_source'] == 'live_aemo' else 'TOU estimate'}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: FUEL RUN
# ═══════════════════════════════════════════════════════════════════════════════
with tab_fuel:
    if r is None:
        st.info("Run analysis first.", icon="ℹ️")
    else:
        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.plotly_chart(fuel_chart(r["fuel_pumps"], r["best_pump"]),
                            use_container_width=True, config={"displayModeBar": False})

            st.markdown("#### All Stations")
            sorted_pumps = sorted(r["fuel_pumps"], key=lambda x: x["price"])
            for p in sorted_pumps:
                is_best = p["name"] == r["best_pump"]["name"]
                icon = "🥇" if is_best else "  "
                src  = " *(est.)*" if p.get("source") == "synthetic" else ""
                st.markdown(
                    f"{icon} **{p['name']}** — `${p['price']:.3f}/L`  "
                    f"<span style='color:#475569'>{p.get('address','')}{src}</span>",
                    unsafe_allow_html=True,
                )

        with col_right:
            st.markdown("#### 🏍️ Detour Decision")
            dec = r["decision"]
            if dec["profitable"]:
                st.success(f"**GO** · Net saving **+${dec['net_profit']:.2f}**")
            else:
                st.warning(f"**STAY** · Net cost **${abs(dec['net_profit']):.2f}**")

            st.caption(dec["logic"])

            st.write("")
            rt = r["route"]
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Distance",    f"{rt['distance_km']} km")
            rc2.metric("Round-trip",  f"{rt['round_trip_km']} km")
            rc3.metric("Est. time",   f"{rt['duration_min']:.0f} min")

            st.write("")
            st.markdown("#### 🌐 Macro Context")
            mac = r["macro"]
            st.plotly_chart(
                macro_gauge(mac["brent_crude_usd"], mac["brent_change_pct"], mac["crude_trend"]),
                use_container_width=True, config={"displayModeBar": False},
            )
            trend_icon = {"RISING": "🔺", "FALLING": "🔻", "STABLE": "➡️"}
            st.markdown(f"{trend_icon.get(mac['crude_trend'], '')} **{mac['crude_trend']}** · AUD/USD {mac['aud_usd']:.4f}")
            st.caption(mac["recommendation"])
            if mac["data_source"] == "fallback":
                st.warning("Using fallback market data — yfinance unavailable", icon="⚠️")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: RIDING
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ride:
    if r is None:
        st.info("Run analysis first.", icon="ℹ️")
    else:
        ride = r["ride"]
        col_score, col_chart = st.columns([1, 2])

        with col_score:
            score = ride["overall_day_score"]
            if score >= 70:
                st.success(f"### 🏍️ {score:.0f}/100", icon=None)
                st.markdown("**Great day to ride!**")
            elif score >= 45:
                st.warning(f"### 🌤️ {score:.0f}/100", icon=None)
                st.markdown("**Decent conditions**")
            else:
                st.error(f"### 🌧️ {score:.0f}/100", icon=None)
                st.markdown("**Not ideal**")

            st.write("")
            st.markdown(f"**{ride['recommendation']}**")

            if ride["best_window_start"] is not None:
                st.write("")
                st.metric("Best window",
                          f"{ride['best_window_start']}:00 – {ride['best_window_start'] + 2}:00")

            # Best hour conditions
            best_h = next(
                (h for h in ride["hourly_scores"] if h.get("score") == ride["best_hour_score"]),
                None
            )
            if best_h:
                st.write("")
                st.markdown("**Peak hour conditions:**")
                if best_h.get("temp_c") is not None:
                    st.caption(f"🌡️ {best_h['temp_c']}°C · 💨 {best_h['wind_kmh']} km/h · "
                               f"🌧️ {best_h['rain_prob_pct']}% rain · ☁️ {best_h['cloud_pct']}% cloud")

        with col_chart:
            ride_fig = ride_chart(ride)
            if ride_fig:
                st.plotly_chart(ride_fig, use_container_width=True, config={"displayModeBar": False})

        # Detailed hourly table
        with st.expander("Hourly details"):
            valid_hours = [h for h in ride["hourly_scores"] if h.get("score", 0) > 0]
            if valid_hours:
                import pandas as pd
                df = pd.DataFrame([
                    {
                        "Hour": f"{h['hour']}:00",
                        "Score": f"{h['score']:.0f}",
                        "Temp °C": h.get("temp_c", ""),
                        "Wind km/h": h.get("wind_kmh", ""),
                        "Rain %": h.get("rain_prob_pct", ""),
                        "Cloud %": h.get("cloud_pct", ""),
                    }
                    for h in valid_hours
                ])
                st.dataframe(df, hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: AGENT FLOW GRAPH
# ═══════════════════════════════════════════════════════════════════════════════
with tab_flow:
    # Build agent_states from traces
    states = {}
    for t in st.session_state.traces:
        if t["event"] == "agent_complete":
            states[t["agent"]] = "done"

    if not states:
        st.info("Run analysis to see the agent flow graph animate.", icon="ℹ️")

    col_graph, col_legend = st.columns([3, 1])
    with col_graph:
        st.plotly_chart(agent_flow_graph(states), use_container_width=True,
                        config={"displayModeBar": False})

    with col_legend:
        st.markdown("#### Agent Status")
        st.write("")
        agents_info = [
            ("🎯 Orchestrator",    "Coordinates all agents"),
            ("☀️ Solar Analyst",   "Open-Meteo irradiance"),
            ("🔋 Battery Manager", "Charge/discharge logic"),
            ("⚡ Grid Arbitrage",  "AEMO NEM spot price"),
            ("⛽ Fuel Scout",      "NSW FuelCheck prices"),
            ("🗺️ Logistics",       "OSRM route distance"),
            ("🏍️ MT-10 Calc",      "Detour profitability"),
            ("🌐 Macro & FX",      "Brent Crude / AUD"),
            ("🌤️ Ride Scout",      "Weather ride scorer"),
            ("🧠 Claude Advisor",  "LLM synthesis"),
        ]
        for label, desc in agents_info:
            agent_key = label.split()[1] if " " in label else label
            status = states.get(agent_key, "idle")
            icon = "🟢" if status == "done" else "⚪"
            st.markdown(f"{icon} **{label}**")
            st.caption(f"  {desc}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6: CHAT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    # Suggested questions (show only on first load)
    if len(st.session_state.chat_messages) <= 1:
        st.markdown("**Quick questions:**")
        suggestions = [
            "Should I ride today?",
            "Is the fuel detour worth it?",
            "Should I export solar or store it?",
            "What does today look like overall?",
        ]
        cols = st.columns(len(suggestions))
        for i, (col, suggestion) in enumerate(zip(cols, suggestions)):
            if col.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": suggestion})
                with st.spinner("Thinking…"):
                    response = "".join(stream_chat(st.session_state.chat_messages, r))
                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                st.rerun()
        st.divider()

    # Chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"], avatar="🧠" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Ask about solar, fuel, riding conditions, grid…"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🧠"):
            response = st.write_stream(
                stream_chat(st.session_state.chat_messages, r)
            )
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7: TRACE LOG
# ═══════════════════════════════════════════════════════════════════════════════
with tab_trace:
    if not st.session_state.traces:
        st.info("Run analysis to see agent trace events.", icon="ℹ️")
    else:
        st.markdown(f"**{len(st.session_state.traces)} trace events**")
        for i, t in enumerate(st.session_state.traces):
            with st.expander(
                f"{'✅' if t['event'] == 'agent_complete' else '▶️'} "
                f"**{t['agent']}** — `{t['event']}`",
                expanded=False,
            ):
                st.json(t.get("data", {}), expanded=1)
