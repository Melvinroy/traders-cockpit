from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps_auth import require_websocket_session
from app.api import (
    routes_account,
    routes_broker,
    routes_market,
    routes_positions,
    routes_trade,
)
from app.api.routes_auth import router as auth_router
from app.core.config import Settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.auth import get_auth_store
from app.services.cockpit import CockpitService
from app.ws.manager import WebSocketManager

settings = Settings.from_env()
settings.validate_runtime()
ws_manager = WebSocketManager(settings.redis_url, settings.redis_channel_prefix)
service = CockpitService(settings, ws_manager)
auth_store = get_auth_store(settings)


async def reconcile_heartbeat_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        interval = settings.reconcile_slow_interval_seconds
        try:
            with SessionLocal() as db:
                service.run_reconcile_heartbeat(db)
                interval = service.next_reconcile_interval_seconds(db)
        except Exception:
            interval = settings.reconcile_slow_interval_seconds
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ws_manager.start()
    reconcile_stop = asyncio.Event()
    reconcile_task: asyncio.Task[None] | None = None
    if settings.uses_sqlite:
        Base.metadata.create_all(bind=engine)
    auth_store.bootstrap_users(
        admin_username=settings.auth_admin_username,
        admin_password=settings.auth_admin_password,
        trader_username=settings.auth_trader_username,
        trader_password=settings.auth_trader_password,
        seed_enabled=settings.auth_seed_users,
    )
    with SessionLocal() as db:
        service.ensure_seed_data(db)
    if not settings.uses_sqlite:
        reconcile_task = asyncio.create_task(reconcile_heartbeat_loop(reconcile_stop))
    yield
    reconcile_stop.set()
    if reconcile_task is not None:
        await reconcile_task
    await ws_manager.stop()


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
app.include_router(routes_broker.build_router(service))
app.include_router(routes_market.build_router(service))
app.include_router(routes_positions.build_router(service))
app.include_router(routes_trade.build_router(service))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "broker_mode": settings.broker_mode}


@app.websocket("/ws/cockpit")
async def cockpit_ws(websocket: WebSocket) -> None:
    try:
        await require_websocket_session(websocket)
    except RuntimeError:
        return
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
