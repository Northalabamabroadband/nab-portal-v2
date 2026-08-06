from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from app.core.settings import get_settings
from app.modules.uisp.client import UISPClient

settings = get_settings()
_DEVICE_CACHE_LOCK = asyncio.Lock()
_DEVICE_CACHE: list[dict[str, Any]] = []
_DEVICE_CACHE_LOADED_AT = 0.0
_DEVICE_CACHE_LOADED_AT_ISO: str | None = None
_DEVICE_CACHE_LAST_ERROR: str | None = None
_EMPTY_VALUES = (None, "", [], {})


def first_value(
    record: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def path_value(
    record: dict[str, Any],
    *paths: str | tuple[str, ...],
    default: Any = None,
) -> Any:
    for path in paths:
        parts = path.split(".") if isinstance(path, str) else path
        current: Any = record
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                break
            current = current[part]
        else:
            if current not in _EMPTY_VALUES:
                return current
    return default


def deep_value(
    record: dict[str, Any],
    *keys: str,
    default: Any = None,
    max_depth: int = 5,
) -> Any:
    wanted = {key.casefold() for key in keys}
    queue: list[tuple[Any, int]] = [(record, 0)]
    visited = 0

    while queue and visited < 500:
        current, depth = queue.pop(0)
        visited += 1
        if isinstance(current, dict):
            for key, value in current.items():
                if (
                    str(key).casefold() in wanted
                    and value not in _EMPTY_VALUES
                ):
                    return value
            if depth < max_depth:
                queue.extend(
                    (value, depth + 1)
                    for value in current.values()
                    if isinstance(value, (dict, list))
                )
        elif isinstance(current, list) and depth < max_depth:
            queue.extend(
                (value, depth + 1)
                for value in current
                if isinstance(value, (dict, list))
            )

    return default


def telemetry_value(
    record: dict[str, Any],
    paths: tuple[str, ...],
    aliases: tuple[str, ...],
) -> Any:
    value = path_value(record, *paths)
    if value not in _EMPTY_VALUES:
        return value
    return deep_value(record, *aliases)


def normalize_status(record: dict[str, Any]) -> str:
    raw_value = telemetry_value(
        record,
        (
            "overview.status",
            "overview.connectionStatus",
            "identification.status",
            "status",
            "state",
            "connectionStatus",
            "deviceStatus",
        ),
        ("connectionStatus", "deviceStatus", "status", "state"),
    )
    raw = as_text(raw_value, "unknown").strip().lower()

    if raw in {
        "1",
        "online",
        "active",
        "connected",
        "up",
        "ok",
        "operational",
    }:
        return "online"
    if raw in {
        "0",
        "offline",
        "inactive",
        "disconnected",
        "down",
        "failed",
        "unreachable",
    }:
        return "offline"
    if raw in {"warning", "degraded", "unstable"}:
        return "warning"

    online = telemetry_value(
        record,
        (
            "overview.isOnline",
            "overview.connected",
            "isOnline",
            "connected",
        ),
        ("isOnline", "connected"),
    )
    if online is True or str(online).strip().lower() == "true":
        return "online"
    if online is False or str(online).strip().lower() == "false":
        return "offline"

    return "unknown"


def number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = first_value(
            value,
            "value",
            "current",
            "last",
            "average",
            "avg",
            "usage",
            "utilization",
            "rate",
            "seconds",
        )
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        if not isinstance(value, str):
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None


def text_metric(
    record: dict[str, Any],
    paths: tuple[str, ...],
    aliases: tuple[str, ...],
) -> str | None:
    value = telemetry_value(record, paths, aliases)
    text = as_text(value).strip()
    return text or None


def timestamp_metric(
    record: dict[str, Any],
    paths: tuple[str, ...],
    aliases: tuple[str, ...],
) -> str | None:
    value = telemetry_value(record, paths, aliases)
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(
                seconds,
                tz=timezone.utc,
            ).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    text = as_text(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return text
    seconds = numeric / 1000 if numeric > 10_000_000_000 else numeric
    try:
        return datetime.fromtimestamp(
            seconds,
            tz=timezone.utc,
        ).isoformat()
    except (OverflowError, OSError, ValueError):
        return text


def number_metric(
    record: dict[str, Any],
    paths: tuple[str, ...],
    aliases: tuple[str, ...],
) -> float | None:
    return number(telemetry_value(record, paths, aliases))


def normalize_device(record: dict[str, Any]) -> dict[str, Any]:
    device_id = as_text(
        path_value(
            record,
            "id",
            "_id",
            "deviceId",
            "identification.id",
            "device.id",
            default=deep_value(record, "deviceId", "_id"),
        )
    )
    cpu = number_metric(
        record,
        (
            "overview.cpu",
            "overview.cpuUsage",
            "overview.cpuLoad",
            "statistics.cpu",
            "statistics.cpuUsage",
            "cpu",
            "cpuUsage",
            "cpuLoad",
        ),
        ("cpuUsage", "cpuLoad", "cpu"),
    )
    memory = number_metric(
        record,
        (
            "overview.ram",
            "overview.ramUsage",
            "overview.memory",
            "overview.memoryUsage",
            "statistics.ram",
            "statistics.memory",
            "memory",
            "memoryUsage",
            "ramUsage",
        ),
        ("ramUsage", "memoryUsage", "memory", "ram"),
    )
    temperature = number_metric(
        record,
        (
            "overview.temperature",
            "overview.boardTemperature",
            "statistics.temperature",
            "temperature",
            "temp",
            "boardTemperature",
        ),
        ("boardTemperature", "temperature", "temp"),
    )
    signal = number_metric(
        record,
        (
            "overview.signal",
            "overview.signalStrength",
            "overview.rssi",
            "wireless.signal",
            "wireless.signalStrength",
            "wireless.rssi",
            "signal",
            "signalStrength",
            "rssi",
        ),
        ("signalStrength", "signal", "rssi"),
    )
    latency = number_metric(
        record,
        (
            "overview.latency",
            "overview.ping",
            "overview.pingLatency",
            "statistics.latency",
            "latency",
            "pingLatency",
        ),
        ("pingLatency", "latency"),
    )
    packet_loss = number_metric(
        record,
        (
            "overview.packetLoss",
            "overview.packet_loss",
            "statistics.packetLoss",
            "packetLoss",
            "packet_loss",
            "loss",
        ),
        ("packetLoss", "packet_loss"),
    )
    uptime_seconds = number_metric(
        record,
        (
            "overview.uptime",
            "overview.uptimeSeconds",
            "statistics.uptime",
            "uptime",
            "uptimeSeconds",
        ),
        ("uptimeSeconds", "uptime"),
    )
    rx_rate_bps = number_metric(
        record,
        (
            "overview.rxRate",
            "overview.receiveRate",
            "overview.rxBytesPerSecond",
            "overview.throughput.rx",
            "statistics.rxRate",
            "statistics.throughput.rx",
            "rxRate",
            "receiveRate",
            "rxBytesPerSecond",
        ),
        (
            "rxBytesPerSecond",
            "receiveRate",
            "rxRate",
            "downlinkRate",
        ),
    )
    tx_rate_bps = number_metric(
        record,
        (
            "overview.txRate",
            "overview.transmitRate",
            "overview.txBytesPerSecond",
            "overview.throughput.tx",
            "statistics.txRate",
            "statistics.throughput.tx",
            "txRate",
            "transmitRate",
            "txBytesPerSecond",
        ),
        (
            "txBytesPerSecond",
            "transmitRate",
            "txRate",
            "uplinkRate",
        ),
    )
    last_seen_at = timestamp_metric(
        record,
        (
            "overview.lastSeenAt",
            "overview.lastSeen",
            "overview.lastContact",
            "statistics.lastSeenAt",
            "lastSeenAt",
            "lastSeen",
            "lastContact",
        ),
        ("lastSeenAt", "lastSeen", "lastContact"),
    )
    site_value = telemetry_value(
        record,
        (
            "identification.site",
            "overview.site",
            "site",
        ),
        ("site",),
    )
    site_record = site_value if isinstance(site_value, dict) else {}
    customer_count = number_metric(
        record,
        (
            "overview.clientCount",
            "overview.customerCount",
            "statistics.clientCount",
            "clientCount",
            "customerCount",
        ),
        ("clientCount", "customerCount"),
    )
    telemetry = (
        cpu,
        memory,
        temperature,
        signal,
        latency,
        packet_loss,
        uptime_seconds,
        rx_rate_bps,
        tx_rate_bps,
        last_seen_at,
    )

    return {
        "id": device_id,
        "name": as_text(
            telemetry_value(
                record,
                (
                    "identification.name",
                    "identification.hostname",
                    "identification.systemName",
                    "identification",
                    "overview.name",
                    "name",
                    "displayName",
                    "hostname",
                    "systemName",
                ),
                ("displayName", "hostname", "systemName"),
            ),
            f"Device {device_id}",
        ),
        "model": as_text(
            telemetry_value(
                record,
                (
                    "identification.modelName",
                    "identification.model",
                    "identification.product",
                    "identification.platform",
                    "modelName",
                    "model",
                    "product",
                ),
                ("modelName", "model", "product", "platform"),
            ),
            "Unknown",
        ),
        "type": as_text(
            telemetry_value(
                record,
                (
                    "identification.role",
                    "identification.type",
                    "identification.deviceType",
                    "type",
                    "deviceType",
                    "category",
                ),
                ("deviceType", "role", "category", "type"),
            ),
            "network",
        ),
        "status": normalize_status(record),
        "site_id": as_text(
            path_value(
                site_record,
                "id",
                default=telemetry_value(
                    record,
                    ("identification.siteId", "siteId"),
                    ("siteId",),
                ),
            )
        ),
        "site_name": as_text(
            path_value(
                site_record,
                "name",
                "displayName",
                default=telemetry_value(
                    record,
                    ("identification.siteName", "siteName"),
                    ("siteName",),
                ),
            ),
            "Unknown site",
        ),
        "ip": text_metric(
            record,
            (
                "identification.ipAddress",
                "identification.ip",
                "overview.ipAddress",
                "overview.ip",
                "ipAddress",
                "primaryIp",
                "ip",
            ),
            ("ipAddress", "primaryIp", "ip"),
        ),
        "mac": text_metric(
            record,
            (
                "identification.mac",
                "identification.macAddress",
                "overview.mac",
                "mac",
                "macAddress",
            ),
            ("macAddress", "mac"),
        ),
        "firmware": text_metric(
            record,
            (
                "identification.firmwareVersion",
                "identification.firmware",
                "overview.firmwareVersion",
                "firmwareVersion",
                "firmware",
                "version",
            ),
            ("firmwareVersion", "firmware"),
        ),
        "cpu": cpu,
        "memory": memory,
        "temperature": temperature,
        "signal": signal,
        "latency": latency,
        "packet_loss": packet_loss,
        "uptime_seconds": uptime_seconds,
        "rx_rate_bps": rx_rate_bps,
        "tx_rate_bps": tx_rate_bps,
        "last_seen_at": last_seen_at,
        "telemetry_fields": sum(value is not None for value in telemetry),
        "customer_count": int(customer_count or 0),
        "latitude": number_metric(
            record,
            (
                "identification.site.location.latitude",
                "site.location.latitude",
                "location.latitude",
                "latitude",
                "lat",
            ),
            ("latitude", "lat"),
        ),
        "longitude": number_metric(
            record,
            (
                "identification.site.location.longitude",
                "site.location.longitude",
                "location.longitude",
                "longitude",
                "lon",
                "lng",
            ),
            ("longitude", "lon", "lng"),
        ),
        "raw": record,
    }


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in (
            "name",
            "displayName",
            "hostname",
            "systemName",
            "value",
            "id",
        ):
            nested = value.get(key)
            if isinstance(nested, str) and nested:
                return nested
        return default
    return str(value)


def derive_alarms(
    devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alarms: list[dict[str, Any]] = []

    for device in devices:
        base = {
            "device_id": device["id"],
            "device_name": device["name"],
            "site_name": device["site_name"],
            "customers_affected": device["customer_count"],
        }

        if device["status"] == "offline":
            alarms.append({
                **base,
                "severity": "critical",
                "type": "device_offline",
                "title": f"{device['name']} is offline",
                "detail": "UISP reports this network device as offline.",
            })

        if device["cpu"] is not None and device["cpu"] >= 90:
            alarms.append({
                **base,
                "severity": "warning",
                "type": "high_cpu",
                "title": f"High CPU on {device['name']}",
                "detail": f"CPU utilization is {device['cpu']:.0f}%.",
            })

        if (
            device["temperature"] is not None
            and device["temperature"] >= 75
        ):
            alarms.append({
                **base,
                "severity": "warning",
                "type": "high_temperature",
                "title": f"High temperature on {device['name']}",
                "detail": (
                    f"Device temperature is "
                    f"{device['temperature']:.1f}."
                ),
            })

        if (
            device["packet_loss"] is not None
            and device["packet_loss"] >= 10
        ):
            alarms.append({
                **base,
                "severity": "warning",
                "type": "packet_loss",
                "title": f"Packet loss on {device['name']}",
                "detail": (
                    f"Packet loss is {device['packet_loss']:.1f}%."
                ),
            })

        if device["latency"] is not None and device["latency"] >= 100:
            alarms.append({
                **base,
                "severity": "warning",
                "type": "high_latency",
                "title": f"High latency on {device['name']}",
                "detail": f"Latency is {device['latency']:.1f} ms.",
            })

        if device["signal"] is not None and device["signal"] <= -75:
            alarms.append({
                **base,
                "severity": "warning",
                "type": "weak_signal",
                "title": f"Weak signal on {device['name']}",
                "detail": f"Signal level is {device['signal']:.1f} dBm.",
            })

    alarms.sort(
        key=lambda alarm: (
            0 if alarm["severity"] == "critical" else 1,
            alarm["device_name"],
        )
    )
    return alarms


def device_cache_metadata() -> dict[str, Any]:
    age = (
        max(0.0, monotonic() - _DEVICE_CACHE_LOADED_AT)
        if _DEVICE_CACHE_LOADED_AT
        else None
    )
    ttl = max(2.0, settings.network_uisp_cache_seconds)
    return {
        "loaded_at": _DEVICE_CACHE_LOADED_AT_ISO,
        "age_seconds": round(age, 2) if age is not None else None,
        "ttl_seconds": ttl,
        "fresh": age is not None and age < ttl,
        "device_count": len(_DEVICE_CACHE),
        "last_error": _DEVICE_CACHE_LAST_ERROR,
    }


async def load_devices(
    limit: int = 500,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    global _DEVICE_CACHE
    global _DEVICE_CACHE_LOADED_AT
    global _DEVICE_CACHE_LOADED_AT_ISO
    global _DEVICE_CACHE_LAST_ERROR

    bounded_limit = min(max(limit, 1), 2000)
    ttl = max(2.0, settings.network_uisp_cache_seconds)
    request_started = monotonic()
    now = request_started
    if (
        not force
        and _DEVICE_CACHE_LOADED_AT
        and now - _DEVICE_CACHE_LOADED_AT < ttl
    ):
        return deepcopy(_DEVICE_CACHE[:bounded_limit])

    async with _DEVICE_CACHE_LOCK:
        now = monotonic()
        if force and _DEVICE_CACHE_LOADED_AT > request_started:
            return deepcopy(_DEVICE_CACHE[:bounded_limit])
        if (
            not force
            and _DEVICE_CACHE_LOADED_AT
            and now - _DEVICE_CACHE_LOADED_AT < ttl
        ):
            return deepcopy(_DEVICE_CACHE[:bounded_limit])

        uisp = UISPClient("nms")
        try:
            records = await uisp.nms_devices(2000)
        except Exception as exc:
            _DEVICE_CACHE_LAST_ERROR = str(exc)
            if _DEVICE_CACHE_LOADED_AT:
                return deepcopy(_DEVICE_CACHE[:bounded_limit])
            raise
        devices = [
            normalize_device(record)
            for record in records
        ]
        _DEVICE_CACHE = devices
        _DEVICE_CACHE_LOADED_AT = monotonic()
        _DEVICE_CACHE_LOADED_AT_ISO = (
            datetime.now(timezone.utc).isoformat()
        )
        _DEVICE_CACHE_LAST_ERROR = None
        return deepcopy(devices[:bounded_limit])


async def overview(
    limit: int = 500,
    *,
    force: bool = False,
) -> dict[str, Any]:
    devices = await load_devices(limit, force=force)
    alarms = derive_alarms(devices)

    online = sum(device["status"] == "online" for device in devices)
    offline = sum(device["status"] == "offline" for device in devices)
    warning = sum(device["status"] == "warning" for device in devices)
    unknown = len(devices) - online - offline - warning

    customer_impact = sum(
        alarm["customers_affected"]
        for alarm in alarms
        if alarm["type"] == "device_offline"
    )

    site_names = sorted({
        device["site_name"]
        for device in devices
        if device["site_name"]
        and device["site_name"] != "Unknown site"
    })

    return {
        "summary": {
            "devices_total": len(devices),
            "devices_online": online,
            "devices_offline": offline,
            "devices_warning": warning,
            "devices_unknown": unknown,
            "sites_total": len(site_names),
            "active_alarms": len(alarms),
            "critical_alarms": sum(
                alarm["severity"] == "critical"
                for alarm in alarms
            ),
            "customers_affected": customer_impact,
            "devices_reporting_telemetry": sum(
                int(device.get("telemetry_fields") or 0) > 0
                for device in devices
            ),
        },
        "devices": devices,
        "alarms": alarms,
        "sites": site_names,
        "cache": device_cache_metadata(),
    }


async def topology(
    limit: int = 500,
    *,
    force: bool = False,
) -> dict[str, Any]:
    devices = await load_devices(limit, force=force)
    sites: dict[str, dict[str, Any]] = {}

    for device in devices:
        site_name = device["site_name"] or "Unknown site"
        site = sites.setdefault(
            site_name,
            {
                "name": site_name,
                "devices": [],
                "online": 0,
                "offline": 0,
                "customers": 0,
                "latitude": device.get("latitude"),
                "longitude": device.get("longitude"),
            },
        )

        site["devices"].append(device["id"])
        site["customers"] += device["customer_count"]

        if device["status"] == "online":
            site["online"] += 1
        elif device["status"] == "offline":
            site["offline"] += 1

    return {
        "sites": list(sites.values()),
        "links": [],
        "device_count": len(devices),
        "cache": device_cache_metadata(),
    }
