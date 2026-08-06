from __future__ import annotations

import asyncio
import json

from app.core.redis_client import redis_client
from app.modules.live.manager import manager
from app.modules.mikrotik.collector import COLLECTOR_CHANNEL


class MikroTikEventFanout:
    def __init__(self) -> None:
        self.running = False
        self.detail = "Fan-out has not started"
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self.running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            except asyncio.CancelledError:
                pass
        self.running = False

    async def _run(self) -> None:
        while not self._stop.is_set():
            pubsub = None
            try:
                pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
                await asyncio.to_thread(pubsub.subscribe, COLLECTOR_CHANNEL)
                self.detail = "Subscribed to Redis MikroTik telemetry"
                while not self._stop.is_set():
                    message = await asyncio.to_thread(
                        pubsub.get_message,
                        timeout=1.0,
                    )
                    if not message or message.get("type") != "message":
                        continue
                    payload = json.loads(message["data"])
                    if isinstance(payload, dict):
                        await manager.broadcast(payload)
            except Exception as exc:
                self.detail = f"Redis fan-out reconnecting: {exc}"
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
            finally:
                if pubsub is not None:
                    await asyncio.to_thread(pubsub.close)
        self.running = False


fanout = MikroTikEventFanout()
