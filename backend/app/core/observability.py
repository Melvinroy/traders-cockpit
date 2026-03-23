from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_client_session_id_ctx: ContextVar[str | None] = ContextVar("client_session_id", default=None)
logger = logging.getLogger("traders_cockpit")


def resolve_request_id(candidate: str | None) -> str:
    value = (candidate or "").strip()
    return value[:128] if value else uuid4().hex


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id_ctx.set(request_id)


def bind_client_session_id(client_session_id: str | None) -> Token[str | None]:
    return _client_session_id_ctx.set(client_session_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_ctx.reset(token)


def reset_client_session_id(token: Token[str | None]) -> None:
    _client_session_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def get_client_session_id() -> str | None:
    return _client_session_id_ctx.get()


def request_log_fields(request: Request | None = None, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": get_request_id(),
    }
    client_session_id = get_client_session_id()
    if client_session_id is not None:
        payload["client_session_id"] = client_session_id
    if request is not None:
        payload["method"] = request.method
        payload["path"] = request.url.path
        payload["client_ip"] = request.client.host if request.client else None
    payload.update(fields)
    return payload


def log_event(event: str, level: str = "info", **fields: Any) -> None:
    payload = {
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "event": event,
        **fields,
    }
    message = json.dumps(payload, default=str, sort_keys=True)
    getattr(logger, level, logger.info)(message)
