from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.core.redis_client import redis_client
from app.core.settings import get_settings
from app.models.mikrotik import MikroTikInterfaceRollup
from app.modules.mikrotik.client import (
    MikroTikClient,
    MikroTikError,
    RouterProfile,
    load_router_profiles,
    router_profile,
)

settings = get_settings()

COLLECTOR_LEASE_KEY = "mikrotik:collector:lease:v2"
COLLECTOR_CHANNEL = "mikrotik:events:v2"
STATUS_KEY_PREFIX = "mikrotik:status:v2:"
HISTORY_KEY_PREFIX = "mikrotik:history:v2:"


def _counter(value: Any) -> int:
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def calculate_interface_rates(
    rows: list[dict[str, Any]],
    previous: dict[str, tuple[float, int, int]],
    timestamp: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[float, int, int]]]:
    rates: dict[str, dict[str, Any]] = {}
    next_counters: dict[str, tuple[float, int, int]] = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        rx_bytes = _counter(row.get("rx-byte"))
        tx_bytes = _counter(row.get("tx-byte"))
        next_counters[name] = (timestamp, rx_bytes, tx_bytes)
        old = previous.get(name)
        elapsed = timestamp - old[0] if old else 0.0
        rx_delta = rx_bytes - old[1] if old else 0
        tx_delta = tx_bytes - old[2] if old else 0
        rates[name] = {
            "rx": (rx_delta * 8.0 / elapsed) if elapsed > 0 and rx_delta >= 0 else 0.0,
            "tx": (tx_delta * 8.0 / elapsed) if elapsed > 0 and tx_delta >= 0 else 0.0,
            "running": str(row.get("running", "")).lower() == "true",
            "disabled": str(row.get("disabled", "")).lower() == "true",
        }
    return rates, next_counters


@dataclass
class RollupAccumulator:
    router_key: str
    interface_name: str
    bucket_start: datetime
    rx_sum: float = 0.0
    tx_sum: float = 0.0
    rx_peak: float = 0.0
    tx_peak: float = 0.0
    sample_count: int = 0

    def add(self, rx: float, tx: float) -> None:
        self.rx_sum += rx
        self.tx_sum += tx
        self.rx_peak = max(self.rx_peak, rx)
        self.tx_peak = max(self.tx_peak, tx)
        self.sample_count += 1


class MikroTikCollector:
    def __init__(self) -> None:
        self.instance_id = str(uuid4())
        self.running = False
        self.leader = False
        self.detail = "Collector has not started"
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_poll: dict[str, float] = {}
        self._previous: dict[str, dict[str, tuple[float, int, int]]] = {}
        self._rollups: dict[tuple[str, str, datetime], RollupAccumulator] = {}
        self._last_cleanup = 0.0

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self.running = True
        self.detail = "Waiting for Redis collector lease"
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                self._task.cancel()
            except asyncio.CancelledError:
                pass
        await self._flush_rollups(list(self._rollups))
        await self._release_lease()
        self.running = False
        self.leader = False

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    self.leader = await asyncio.to_thread(self._claim_lease)
                    if self.leader:
                        self.detail = "Collecting RouterOS interface telemetry"
                        await self._poll_due_profiles()
                        await self._cleanup_if_due()
                    else:
                        self.detail = "Standby; another API instance owns the collector lease"
                except Exception as exc:
                    self.leader = False
                    self.detail = f"Collector cycle failed: {exc}"
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.running = False

    def _claim_lease(self) -> bool:
        lease_seconds = max(6, settings.mikrotik_collector_lease_seconds)
        acquired = redis_client.set(
            COLLECTOR_LEASE_KEY,
            self.instance_id,
            nx=True,
            ex=lease_seconds,
        )
        if acquired:
            return True
        if redis_client.get(COLLECTOR_LEASE_KEY) == self.instance_id:
            return bool(redis_client.expire(COLLECTOR_LEASE_KEY, lease_seconds))
        return False

    async def _release_lease(self) -> None:
        def release() -> None:
            if redis_client.get(COLLECTOR_LEASE_KEY) == self.instance_id:
                redis_client.delete(COLLECTOR_LEASE_KEY)

        try:
            await asyncio.to_thread(release)
        except Exception:
            pass

    async def _poll_due_profiles(self) -> None:
        profiles = load_router_profiles(include_disabled=True)
        now = monotonic()
        due = []
        for profile in profiles:
            if not profile.enabled:
                await self._store_status(
                    profile,
                    connected=False,
                    detail="Router profile is disabled",
                )
                continue
            if not MikroTikClient(profile).configured():
                await self._store_status(
                    profile,
                    connected=False,
                    detail="Router profile requires a base URL, username, and password",
                )
                continue
            interval = max(2.0, profile.poll_interval_seconds)
            if now - self._last_poll.get(profile.key, 0.0) >= interval:
                self._last_poll[profile.key] = now
                due.append(self._poll_profile(profile))
        if due:
            await asyncio.gather(*due)

    async def _poll_profile(self, profile: RouterProfile) -> None:
        attempted_at = datetime.now(timezone.utc)
        try:
            rows = await MikroTikClient(profile).records("/interface")
            epoch = attempted_at.timestamp()
            rates, counters = calculate_interface_rates(
                rows,
                self._previous.get(profile.key, {}),
                epoch,
            )
            self._previous[profile.key] = counters
            sample = {
                "timestamp": attempted_at.isoformat(),
                "timestamp_ms": int(epoch * 1000),
                "rates": rates,
            }
            await self._store_sample(profile, sample)
            await self._store_status(
                profile,
                connected=True,
                detail="Live collector connected",
                last_seen=attempted_at.isoformat(),
                interface_count=len(rates),
            )
            self._add_rollups(profile.key, attempted_at, rates)
        except Exception as exc:
            detail = str(exc) if isinstance(exc, MikroTikError) else f"Collector error: {exc}"
            await self._store_status(
                profile,
                connected=False,
                detail=detail,
            )

    async def _store_sample(
        self,
        profile: RouterProfile,
        sample: dict[str, Any],
    ) -> None:
        event = {
            "type": "mikrotik.throughput",
            "router_key": profile.key,
            "sample": sample,
        }
        encoded_sample = json.dumps(sample, separators=(",", ":"))
        encoded_event = json.dumps(event, separators=(",", ":"))
        history_key = HISTORY_KEY_PREFIX + profile.key
        history_points = max(20, min(2400, settings.mikrotik_history_points))

        def store() -> None:
            pipeline = redis_client.pipeline()
            pipeline.rpush(history_key, encoded_sample)
            pipeline.ltrim(history_key, -history_points, -1)
            pipeline.expire(history_key, 86400)
            pipeline.publish(COLLECTOR_CHANNEL, encoded_event)
            pipeline.execute()

        await asyncio.to_thread(store)

    async def _store_status(
        self,
        profile: RouterProfile,
        *,
        connected: bool,
        detail: str,
        last_seen: str | None = None,
        interface_count: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        status = {
            "connected": connected,
            "detail": detail,
            "last_attempt_at": now,
            "last_seen": last_seen,
            "interface_count": interface_count,
        }
        status_key = STATUS_KEY_PREFIX + profile.key

        def store() -> None:
            raw = redis_client.get(status_key)
            if raw:
                try:
                    previous = json.loads(raw)
                except json.JSONDecodeError:
                    previous = {}
                if status["last_seen"] is None:
                    status["last_seen"] = previous.get("last_seen")
                if status["interface_count"] is None:
                    status["interface_count"] = previous.get("interface_count")
            redis_client.setex(
                status_key,
                86400,
                json.dumps(status, separators=(",", ":")),
            )

        await asyncio.to_thread(store)

    def _add_rollups(
        self,
        router_key: str,
        timestamp: datetime,
        rates: dict[str, dict[str, Any]],
    ) -> None:
        bucket = timestamp.replace(second=0, microsecond=0)
        finished = [
            key for key in self._rollups
            if key[2] < bucket
        ]
        if finished:
            asyncio.create_task(self._flush_rollups(finished))
        for interface_name, rate in rates.items():
            key = (router_key, interface_name, bucket)
            accumulator = self._rollups.setdefault(
                key,
                RollupAccumulator(router_key, interface_name, bucket),
            )
            accumulator.add(float(rate["rx"]), float(rate["tx"]))

    async def _flush_rollups(
        self,
        keys: list[tuple[str, str, datetime]],
    ) -> None:
        rows = [
            self._rollups.pop(key)
            for key in keys
            if key in self._rollups
        ]
        if not rows:
            return

        def persist() -> None:
            with SessionLocal() as session:
                for row in rows:
                    existing = session.scalar(select(MikroTikInterfaceRollup).where(
                        MikroTikInterfaceRollup.router_key == row.router_key,
                        MikroTikInterfaceRollup.interface_name == row.interface_name,
                        MikroTikInterfaceRollup.bucket_start == row.bucket_start,
                    ))
                    if existing:
                        total = existing.sample_count + row.sample_count
                        existing.rx_average_bps = (
                            existing.rx_average_bps * existing.sample_count + row.rx_sum
                        ) / total
                        existing.tx_average_bps = (
                            existing.tx_average_bps * existing.sample_count + row.tx_sum
                        ) / total
                        existing.rx_peak_bps = max(existing.rx_peak_bps, row.rx_peak)
                        existing.tx_peak_bps = max(existing.tx_peak_bps, row.tx_peak)
                        existing.sample_count = total
                    else:
                        session.add(MikroTikInterfaceRollup(
                            router_key=row.router_key,
                            interface_name=row.interface_name,
                            bucket_start=row.bucket_start,
                            rx_average_bps=row.rx_sum / row.sample_count,
                            tx_average_bps=row.tx_sum / row.sample_count,
                            rx_peak_bps=row.rx_peak,
                            tx_peak_bps=row.tx_peak,
                            sample_count=row.sample_count,
                        ))
                session.commit()

        await asyncio.to_thread(persist)

    async def _cleanup_if_due(self) -> None:
        if monotonic() - self._last_cleanup < 3600:
            return
        self._last_cleanup = monotonic()
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(1, settings.mikrotik_rollup_retention_days)
        )

        def cleanup() -> None:
            with SessionLocal() as session:
                session.execute(delete(MikroTikInterfaceRollup).where(
                    MikroTikInterfaceRollup.bucket_start < cutoff
                ))
                session.commit()

        await asyncio.to_thread(cleanup)

    async def fleet_status(self) -> dict[str, Any]:
        profiles = load_router_profiles(include_disabled=True)
        status_values = await asyncio.gather(*[
            asyncio.to_thread(redis_client.get, STATUS_KEY_PREFIX + profile.key)
            for profile in profiles
        ], return_exceptions=True)
        routers = []
        for profile, raw in zip(profiles, status_values):
            status: dict[str, Any] = {}
            if isinstance(raw, str):
                try:
                    status = json.loads(raw)
                except json.JSONDecodeError:
                    status = {}
            routers.append({
                **profile.public_dict(),
                "connected": bool(status.get("connected")),
                "detail": status.get("detail") or "Waiting for collector telemetry",
                "last_attempt_at": status.get("last_attempt_at"),
                "last_seen": status.get("last_seen"),
                "interface_count": status.get("interface_count"),
            })
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "collector": {
                "enabled": settings.mikrotik_collector_enabled,
                "running": self.running,
                "leader": self.leader,
                "detail": self.detail,
            },
            "routers": routers,
        }

    async def live_history(
        self,
        router_key: str,
        interface_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        router_profile(router_key)
        values = await asyncio.to_thread(
            redis_client.lrange,
            HISTORY_KEY_PREFIX + router_key,
            0,
            -1,
        )
        selected = set(interface_names or [])
        samples = []
        for raw in values:
            try:
                sample = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if selected:
                sample["rates"] = {
                    name: rate
                    for name, rate in sample.get("rates", {}).items()
                    if name in selected
                }
            samples.append(sample)
        return samples

    async def rollup_history(
        self,
        router_key: str,
        minutes: int,
        interface_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        router_profile(router_key)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        def query() -> list[MikroTikInterfaceRollup]:
            with SessionLocal() as session:
                statement = (
                    select(MikroTikInterfaceRollup)
                    .where(
                        MikroTikInterfaceRollup.router_key == router_key,
                        MikroTikInterfaceRollup.bucket_start >= cutoff,
                    )
                    .order_by(MikroTikInterfaceRollup.bucket_start.asc())
                )
                if interface_names:
                    statement = statement.where(
                        MikroTikInterfaceRollup.interface_name.in_(interface_names)
                    )
                return list(session.scalars(statement.limit(10000)).all())

        rows = await asyncio.to_thread(query)
        return [{
            "interface": row.interface_name,
            "bucket_start": row.bucket_start.isoformat(),
            "rx_average_bps": row.rx_average_bps,
            "tx_average_bps": row.tx_average_bps,
            "rx_peak_bps": row.rx_peak_bps,
            "tx_peak_bps": row.tx_peak_bps,
            "sample_count": row.sample_count,
        } for row in rows]


collector = MikroTikCollector()
