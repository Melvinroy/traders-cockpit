from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import suppress
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from redis.asyncio import Redis


class WebSocketManager:
    def __init__(
        self, redis_url: str | None = None, channel_prefix: str = "traders-cockpit"
    ) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._redis_url = redis_url
        self._channel_prefix = channel_prefix
        self._instance_id = uuid4().hex
        self._redis: Redis | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        if not self._redis_url or self._redis is not None:
            return
        try:
            client = Redis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
        except Exception:
            return
        self._redis = client
        self._shutdown.clear()
        self._subscriber_task = asyncio.create_task(self._subscriber_loop(), name="redis-ws-fanout")

    async def stop(self) -> None:
        self._shutdown.set()
        if self._subscriber_task:
            self._subscriber_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._subscriber_task
            self._subscriber_task = None
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.connections[channel].add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            if channel in self.connections:
                self.connections[channel].discard(websocket)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        await self._emit_local(channel, message)
        if self._redis is None:
            return
        try:
            await self._redis.publish(
                self._redis_channel(channel),
                json.dumps(
                    {
                        "instance_id": self._instance_id,
                        "channel": channel,
                        "message": message,
                    }
                ),
            )
        except Exception:
            return

    async def _subscriber_loop(self) -> None:
        if self._redis is None:
            return
        pubsub = self._redis.pubsub()
        channels = [self._redis_channel("cockpit")]
        await pubsub.subscribe(*channels)
        try:
            while not self._shutdown.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue
                payload = self._decode_message(message.get("data"))
                if not payload or payload.get("instance_id") == self._instance_id:
                    continue
                channel = str(payload.get("channel", "cockpit"))
                data = payload.get("message")
                if isinstance(data, dict):
                    await self._emit_local(channel, data)
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(*channels)
            with suppress(Exception):
                await pubsub.aclose()

    async def _emit_local(self, channel: str, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        async with self._lock:
            targets = list(self.connections.get(channel, set()))
        for websocket in targets:
            try:
                await websocket.send_text(encoded)
            except Exception:
                await self.disconnect(channel, websocket)

    def _redis_channel(self, channel: str) -> str:
        return f"{self._channel_prefix}:events:{channel}"

    @staticmethod
    def _decode_message(raw: Any) -> dict[str, Any] | None:
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if isinstance(raw, str):
                return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return None
