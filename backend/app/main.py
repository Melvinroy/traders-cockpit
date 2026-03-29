from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Request
from fastapi.responses import JSONResponse
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
from app.core.observability import (
    REQUEST_ID_HEADER,
    bind_client_session_id,
    bind_request_id,
    log_event,
    request_log_fields,
    reset_client_session_id,
    reset_request_id,
    resolve_request_id,
)
from app.core.startup_preflight import (
    build_dependency_report,
    build_liveness_report,
    build_readiness_report,
)
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = bind_request_id(request_id)
    request.state.request_id = request_id
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        log_event(
            "http.request.failed",
            level="error",
            **request_log_fields(
                request,
                status=500,
                duration_ms=duration_ms,
            ),
        )
        raise
    response.headers[REQUEST_ID_HEADER] = request_id
    duration_ms = round((perf_counter() - started) * 1000, 2)
    log_event(
        "http.request.completed",
        **request_log_fields(
            request,
            status=response.status_code,
            duration_ms=duration_ms,
        ),
    )
    reset_request_id(token)
    return response


app.include_router(auth_router)
app.include_router(routes_account.build_router(service))
app.include_router(routes_broker.build_router(service))
app.include_router(routes_market.build_router(service))
app.include_router(routes_positions.build_router(service))
app.include_router(routes_trade.build_router(service))


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(build_liveness_report(settings))


@app.get("/health/live")
def health_live() -> JSONResponse:
    return JSONResponse(build_liveness_report(settings))


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    payload = build_readiness_report(settings)
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(payload, status_code=status_code)


@app.get("/health/deps")
def health_dependencies() -> JSONResponse:
    payload = {
        "status": "ok",
        "kind": "deps",
        "app_env": settings.app_env,
        "broker_mode": settings.broker_mode,
        "dependencies": build_dependency_report(settings),
    }
    if any(item.get("status") != "ok" for item in payload["dependencies"].values()):
        payload["status"] = "error"
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(payload, status_code=status_code)


@app.websocket("/ws/cockpit")
async def cockpit_ws(websocket: WebSocket) -> None:
    websocket_id = uuid4().hex[:12]
    client_session_id = (websocket.query_params.get("client_session_id") or "").strip() or None
    connection_request_id = resolve_request_id(
        websocket.query_params.get("request_id") or websocket.headers.get(REQUEST_ID_HEADER)
    )
    username: str | None = None
    connected = False
    connect_request_token = bind_request_id(connection_request_id)
    connect_session_token = bind_client_session_id(client_session_id)
    try:
        session = await require_websocket_session(websocket)
    except RuntimeError:
        log_event(
            "ws.auth.failed",
            level="warning",
            **request_log_fields(
                path=websocket.url.path,
                client_ip=websocket.client.host if websocket.client else None,
                websocket_id=websocket_id,
            ),
        )
        reset_client_session_id(connect_session_token)
        reset_request_id(connect_request_token)
        return
    username = str(session["user"]["username"])
    log_event(
        "ws.connect",
        **request_log_fields(
            path=websocket.url.path,
            client_ip=websocket.client.host if websocket.client else None,
            websocket_id=websocket_id,
            username=username,
            channel="cockpit",
        ),
    )
    await ws_manager.connect(
        "cockpit",
        websocket,
        metadata={
            "websocket_id": websocket_id,
            "username": username,
            "client_session_id": client_session_id,
        },
    )
    connected = True
    reset_client_session_id(connect_session_token)
    reset_request_id(connect_request_token)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"action": "noop"}
            action = str(payload.get("action") or "noop")
            message_request_id = resolve_request_id(
                payload.get("requestId") if isinstance(payload.get("requestId"), str) else None
            )
            message_client_session_id = (
                str(payload.get("clientSessionId")).strip()
                if payload.get("clientSessionId") not in (None, "")
                else client_session_id
            )
            message_request_token = bind_request_id(message_request_id)
            message_session_token = bind_client_session_id(message_client_session_id)
            try:
                log_event(
                    "ws.message.received",
                    **request_log_fields(
                        path=websocket.url.path,
                        client_ip=websocket.client.host if websocket.client else None,
                        websocket_id=websocket_id,
                        username=username,
                        channel="cockpit",
                        action=action,
                        symbol=str(payload.get("symbol", "")).upper() or None,
                    ),
                )
                if action == "subscribe_price":
                    with SessionLocal() as db:
                        await service.publish_price_tick(db, str(payload.get("symbol", "")).upper())
            finally:
                reset_client_session_id(message_session_token)
                reset_request_id(message_request_token)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        if connected:
            disconnect_token = bind_request_id(connection_request_id)
            disconnect_session_token = bind_client_session_id(client_session_id)
            log_event(
                "ws.disconnect",
                **request_log_fields(
                    path=websocket.url.path,
                    client_ip=websocket.client.host if websocket.client else None,
                    websocket_id=websocket_id,
                    username=username,
                    channel="cockpit",
                ),
            )
            reset_client_session_id(disconnect_session_token)
            reset_request_id(disconnect_token)
            await ws_manager.disconnect("cockpit", websocket)
