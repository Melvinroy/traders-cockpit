from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_account, routes_market, routes_positions, routes_trade
from app.api.routes_auth import router as auth_router
from app.core.config import Settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.cockpit import CockpitService
from app.ws.manager import WebSocketManager

settings = Settings.from_env()
ws_manager = WebSocketManager()
service = CockpitService(settings, ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        service.ensure_seed_data(db)
    yield


app = FastAPI(title="traders-cockpit", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(routes_account.build_router(service))
app.include_router(routes_market.build_router(service))
app.include_router(routes_positions.build_router(service))
app.include_router(routes_trade.build_router(service))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "broker_mode": settings.broker_mode}


@app.websocket("/ws/cockpit")
async def cockpit_ws(websocket: WebSocket) -> None:
    await ws_manager.connect("cockpit", websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"action": "noop"}
            if payload.get("action") == "subscribe_price":
                with SessionLocal() as db:
                    await service.publish_price_tick(db, str(payload.get("symbol", "")).upper())
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        await ws_manager.disconnect("cockpit", websocket)
