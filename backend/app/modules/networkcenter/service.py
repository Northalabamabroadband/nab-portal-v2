from __future__ import annotations

from typing import Any

from app.modules.uisp.client import UISPClient, UISPError, extract_records


def first_value(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def normalize_status(record: dict[str, Any]) -> str:
    raw = str(
        first_value(
            record,
            "status",
            "state",
            "connectionStatus",
            "deviceStatus",
            default="unknown",
        )
    ).lower()

    if raw in {"1", "online", "active", "connected", "up", "ok"}:
        return "online"
    if raw in {"0", "offline", "inactive", "disconnected", "down", "failed"}:
        return "offline"
    if raw in {"warning", "degraded", "unstable"}:
        return "warning"

    if record.get("isOnline") is True:
        return "online"
    if record.get("isOnline") is False:
        return "offline"

    return "unknown"


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_device(record: dict[str, Any]) -> dict[str, Any]:
    device_id = str(first_value(record, "id", "_id", "deviceId", default=""))
    cpu = number(first_value(record, "cpu", "cpuUsage", "cpuLoad"))
    memory = number(first_value(record, "memory", "memoryUsage", "ramUsage"))
    temperature = number(first_value(record, "temperature", "temp", "boardTemperature"))
    signal = number(first_value(record, "signal", "signalStrength", "rssi"))
    latency = number(first_value(record, "latency", "ping", "pingLatency"))
    packet_loss = number(first_value(record, "packetLoss", "loss"))

    return {
        "id": device_id,
        "name": as_text(first_value(record, "name", "identification", "displayName", "hostname", "systemName", default=f"Device {device_id}"), f"Device {device_id}"),
        "model": as_text(first_value(record, "model", "modelName", "product", default="Unknown"), "Unknown"),
        "type": as_text(first_value(record, "type", "deviceType", "category", default="network"), "network"),
        "status": normalize_status(record),
        "site_id": str(first_value(record, "siteId", "site", default="")),
        "site_name": as_text(first_value(record, "siteName", "site", default="Unknown site"), "Unknown site"),
        "ip": first_value(record, "ipAddress", "ip", "primaryIp"),
        "mac": first_value(record, "mac", "macAddress"),
        "firmware": first_value(record, "firmware", "firmwareVersion", "version"),
        "cpu": cpu,
        "memory": memory,
        "temperature": temperature,
        "signal": signal,
        "latency": latency,
        "packet_loss": packet_loss,
        "customer_count": int(number(first_value(record, "clientCount", "customerCount", "clients", default=0)) or 0),
        "latitude": number(first_value(record, "latitude", "lat")),
        "longitude": number(first_value(record, "longitude", "lon", "lng")),
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
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
        return default
    return str(value)


def derive_alarms(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

        if device["temperature"] is not None and device["temperature"] >= 75:
            alarms.append({
                **base,
                "severity": "warning",
                "type": "high_temperature",
                "title": f"High temperature on {device['name']}",
                "detail": f"Device temperature is {device['temperature']:.1f}.",
            })

        if device["packet_loss"] is not None and device["packet_loss"] >= 10:
            alarms.append({
                **base,
                "severity": "warning",
                "type": "packet_loss",
                "title": f"Packet loss on {device['name']}",
                "detail": f"Packet loss is {device['packet_loss']:.1f}%.",
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


async def load_devices(limit: int = 500) -> list[dict[str, Any]]:
    uisp = UISPClient("nms")

    payload = await uisp.get(
        "/nms/api/v2.1/devices"
    )

    records = extract_records(payload)

    return [
        normalize_device(record)
        for record in records[:min(max(limit, 1), 2000)]
    ]


async def overview(limit: int = 500) -> dict[str, Any]:
    devices = await load_devices(limit)
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
        if device["site_name"] and device["site_name"] != "Unknown site"
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
            "critical_alarms": sum(alarm["severity"] == "critical" for alarm in alarms),
            "customers_affected": customer_impact,
        },
        "devices": devices,
        "alarms": alarms,
        "sites": site_names,
    }


async def topology(limit: int = 500) -> dict[str, Any]:
    devices = await load_devices(limit)
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
    }
