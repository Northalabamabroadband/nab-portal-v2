from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class LiveConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = {
            **event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        stale: list[WebSocket] = []

        async with self.lock:
            for websocket in self.connections:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    stale.append(websocket)

            for websocket in stale:
                self.connections.discard(websocket)


manager = LiveConnectionManager()
