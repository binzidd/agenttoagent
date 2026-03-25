"""
FastAPI server for the Austral Agent Stack.

Endpoints:
  GET  /health            – liveness probe
  GET  /api/solar         – latest solar forecast (no WS needed)
  GET  /api/fuel          – live / synthetic fuel prices
  GET  /api/ride          – today's ride window score
  GET  /api/grid          – NEM spot price + arbitrage advice
  GET  /api/analysis      – full multi-agent result (blocking)
  POST /api/chat          – streaming SSE chat powered by Claude
  WS   /ws                – real-time trace stream + full analysis result

WebSocket message from client:
  { "action": "run" }

WebSocket messages from server:
  { "type": "trace",    "event": "...", "agent": "...", "data": {...}, "timestamp": "..." }
  { "type": "complete", "data": { ... full analysis result ... } }
  { "type": "error",    "message": "..." }

Chat POST /api/chat body:
  { "messages": [{"role": "user", "content": "..."}], "context": <AnalysisResult|null> }
Response: text/event-stream  (SSE), each chunk: data: <token>\\n\\n
"""

import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from orchestrator import AustralOrchestrator
from agents.solar_analyst import SolarAnalyst
from agents.fuel_scout import FuelScoutAgent
from agents.ride_scout import RideScoutAgent
from agents.grid_arbitrage import GridArbitrageAgent
from agents.claude_advisor import stream_chat


class ChatRequest(BaseModel):
    messages: list[dict]          # [{"role": "user"|"assistant", "content": "..."}]
    context: Optional[dict] = None  # latest AnalysisResult, if any


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Austral Agent API starting…")
    yield
    print("🛑 Austral Agent API shutting down.")


app = FastAPI(
    title="Austral Agent Stack API",
    description="Multi-agent system for solar & fuel cost optimisation in Austral, NSW.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REST Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/solar")
async def get_solar():
    return await SolarAnalyst().get_solar_forecast()


@app.get("/api/fuel")
async def get_fuel():
    return await FuelScoutAgent().get_cheapest_p98()


@app.get("/api/ride")
async def get_ride():
    return await RideScoutAgent().get_ride_window()


@app.get("/api/grid")
async def get_grid(battery_fill_pct: float = 50.0):
    return await GridArbitrageAgent().get_arbitrage_advice(battery_fill_pct)


@app.get("/api/analysis")
async def get_analysis():
    """Blocking full analysis – use WebSocket for real-time trace."""
    orchestrator = AustralOrchestrator(send_event=None)
    return await orchestrator.run_full_analysis()


# ─── Chat (SSE streaming) ────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Streaming chat endpoint.  Returns text/event-stream (SSE).
    Each chunk:  data: <token>\\n\\n
    Final chunk: data: [DONE]\\n\\n
    """
    async def generator():
        async for chunk in stream_chat(req.messages, req.context):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send(event: dict):
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("action") == "run":
                try:
                    orchestrator = AustralOrchestrator(send_event=send)
                    result = await orchestrator.run_full_analysis()
                    await websocket.send_text(
                        json.dumps({"type": "complete", "data": result})
                    )
                except Exception as exc:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(exc)})
                    )
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
