from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.connections[channel].add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            if channel in self.connections:
                self.connections[channel].discard(websocket)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        async with self._lock:
            targets = list(self.connections.get(channel, set()))
        for websocket in targets:
            try:
                await websocket.send_text(encoded)
            except Exception:
                await self.disconnect(channel, websocket)
