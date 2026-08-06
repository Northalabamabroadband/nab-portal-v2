from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.core.settings import get_settings
from app.models.operations import CustomerTaucAssignment
from app.modules.auth.dependencies import require_permission
from app.modules.mikrotik.collector import collector
from app.modules.networkcenter.service import (
    device_cache_metadata,
    load_devices,
    overview,
    topology,
)
from app.modules.tauc.client import TAUCClient
from app.modules.tauc.router import cached_snapshot_polling_status
from app.modules.uisp.client import UISPError

router = APIRouter(prefix="/network-center", tags=["network-center-build032"])
settings = get_settings()


@router.get("/polling")
async def coordinated_device_polling(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
    session: Annotated[Session, Depends(database_session)],
    limit: int = Query(default=1000, ge=1, le=2000),
    force: bool = Query(default=False),
) -> dict[str, Any]:
    assignments = list(session.scalars(
        select(CustomerTaucAssignment)
        .order_by(CustomerTaucAssignment.created_at.desc())
        .limit(limit)
    ).all())

    uisp_result, mikrotik_result, tauc_cache_result = await asyncio.gather(
        overview(limit, force=force),
        collector.fleet_status(),
        cached_snapshot_polling_status(),
        return_exceptions=True,
    )

    errors: dict[str, str] = {}
    if isinstance(uisp_result, Exception):
        errors["uisp"] = str(uisp_result)
        uisp: dict[str, Any] = {
            "summary": {},
            "devices": [],
            "alarms": [],
            "sites": [],
            "cache": device_cache_metadata(),
        }
    else:
        uisp = uisp_result
        cache_error = uisp.get("cache", {}).get("last_error")
        if cache_error:
            errors["uisp"] = str(cache_error)

    if isinstance(mikrotik_result, Exception):
        errors["mikrotik"] = str(mikrotik_result)
        mikrotik: dict[str, Any] = {
            "collector": {},
            "routers": [],
        }
    else:
        mikrotik = mikrotik_result
    mikrotik_collector_enabled = bool(
        mikrotik.get("collector", {}).get(
            "enabled",
            settings.mikrotik_collector_enabled,
        )
    )

    if isinstance(tauc_cache_result, Exception):
        errors["tauc"] = str(tauc_cache_result)
        tauc_cache: dict[str, dict] = {}
    else:
        tauc_cache = tauc_cache_result

    devices: list[dict[str, Any]] = []
    for device in uisp.get("devices", []):
        devices.append({
            key: value
            for key, value in {
                **device,
                "id": f"uisp:{device['id']}",
                "source_id": device["id"],
                "source": "uisp",
                "source_label": "UISP NMS",
                "poll_mode": "coalesced-cache",
                "last_polled_at": (
                    uisp.get("cache", {}).get("loaded_at")
                ),
            }.items()
            if key != "raw"
        })

    mikrotik_routers = mikrotik.get("routers", [])
    for router_status in mikrotik_routers:
        enabled = bool(router_status.get("enabled", True))
        connected = bool(router_status.get("connected"))
        devices.append({
            "id": f"mikrotik:{router_status.get('key')}",
            "source_id": str(router_status.get("key") or ""),
            "source": "mikrotik",
            "source_label": "MikroTik",
            "name": str(
                router_status.get("name")
                or router_status.get("key")
                or "MikroTik router"
            ),
            "model": "RouterOS",
            "type": str(router_status.get("role") or "router"),
            "status": (
                "online"
                if connected
                else "offline"
                if (
                    mikrotik_collector_enabled
                    and enabled
                    and router_status.get("configured")
                )
                else "unknown"
            ),
            "site_name": str(
                router_status.get("site") or "Core network"
            ),
            "ip": None,
            "mac": None,
            "firmware": None,
            "cpu": None,
            "memory": None,
            "temperature": None,
            "signal": None,
            "latency": None,
            "packet_loss": None,
            "customer_count": 0,
            "interface_count": int(
                router_status.get("interface_count") or 0
            ),
            "poll_detail": str(
                router_status.get("detail")
                or "Waiting for collector telemetry"
            ),
            "poll_mode": "centralized-collector-cache",
            "poll_interval_seconds": router_status.get(
                "poll_interval_seconds"
            ),
            "last_polled_at": (
                router_status.get("last_seen")
                or router_status.get("last_attempt_at")
            ),
        })

    for assignment in assignments:
        cached = tauc_cache.get(assignment.tauc_device_id, {})
        cached_state = str(cached.get("status") or "").lower()
        devices.append({
            "id": f"tauc:{assignment.tauc_device_id}",
            "source_id": assignment.tauc_device_id,
            "source": "tauc",
            "source_label": "TAUC",
            "name": (
                assignment.network_name
                or assignment.device_model
                or f"Gateway {assignment.serial_number}"
            ),
            "model": assignment.device_model or "Managed gateway",
            "type": "managed_gateway",
            "status": (
                "online"
                if cached_state in {"ready", "online", "connected"}
                else "warning"
                if cached_state in {"partial", "warning", "degraded"}
                else "unknown"
            ),
            "site_name": (
                assignment.network_name
                or f"Customer {assignment.client_id}"
            ),
            "ip": None,
            "mac": assignment.mac_address,
            "firmware": assignment.firmware_version,
            "cpu": None,
            "memory": None,
            "temperature": None,
            "signal": None,
            "latency": None,
            "packet_loss": None,
            "customer_count": int(
                cached.get("connected_devices") or 0
            ),
            "client_id": assignment.client_id,
            "serial_number": assignment.serial_number,
            "network_id": (
                cached.get("network_id")
                or assignment.network_id
            ),
            "wifi_networks": int(cached.get("wifi_networks") or 0),
            "warning_count": int(cached.get("warning_count") or 0),
            "poll_detail": (
                "Fresh managed Wi-Fi snapshot cache"
                if cached
                else "Assigned; snapshot is refreshed on demand"
            ),
            "poll_mode": "rate-limited-snapshot-cache",
            "poll_interval_seconds": (
                settings.tauc_min_request_interval_seconds
            ),
            "last_polled_at": cached.get("generated_at"),
            "cache_age_seconds": cached.get("cache_age_seconds"),
            "cache_remaining_seconds": cached.get(
                "cache_remaining_seconds"
            ),
        })

    alarms = [
        {
            **alarm,
            "source": "uisp",
            "source_label": "UISP NMS",
        }
        for alarm in uisp.get("alarms", [])
    ]
    for router_status in mikrotik_routers:
        if (
            mikrotik_collector_enabled
            and router_status.get("enabled", True)
            and router_status.get("configured")
            and not router_status.get("connected")
        ):
            alarms.append({
                "severity": "critical",
                "type": "router_unavailable",
                "title": (
                    f"{router_status.get('name') or 'MikroTik router'} "
                    "collector is offline"
                ),
                "detail": str(
                    router_status.get("detail")
                    or "No current RouterOS collector data."
                ),
                "device_id": str(router_status.get("key") or ""),
                "device_name": str(
                    router_status.get("name") or "MikroTik router"
                ),
                "site_name": str(
                    router_status.get("site") or "Core network"
                ),
                "customers_affected": 0,
                "source": "mikrotik",
                "source_label": "MikroTik",
            })

    statuses = [device["status"] for device in devices]
    tauc_configuration = TAUCClient().configuration_status()
    uisp_cache = uisp.get("cache", device_cache_metadata())
    uisp_state = (
        "degraded"
        if errors.get("uisp") or not uisp_cache.get("fresh")
        else "online"
    )
    connected_routers = sum(
        bool(row.get("connected"))
        for row in mikrotik_routers
    )
    configured_routers = sum(
        bool(row.get("configured") and row.get("enabled", True))
        for row in mikrotik_routers
    )
    mikrotik_state = (
        "offline"
        if errors.get("mikrotik")
        else "unconfigured"
        if not mikrotik_collector_enabled
        else "degraded"
        if configured_routers and connected_routers < configured_routers
        else "online"
        if connected_routers
        else "unconfigured"
    )
    tauc_state = (
        "degraded"
        if errors.get("tauc")
        else "online"
        if tauc_configuration.get("configured")
        else "unconfigured"
    )
    source_states = [uisp_state, mikrotik_state, tauc_state]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "poll_interval_seconds": max(
            5,
            settings.network_dashboard_poll_seconds,
        ),
        "mode": "coordinated-multi-source-cache",
        "summary": {
            "devices_total": len(devices),
            "devices_online": statuses.count("online"),
            "devices_offline": statuses.count("offline"),
            "devices_warning": statuses.count("warning"),
            "devices_unknown": statuses.count("unknown"),
            "sites_total": len({
                device["site_name"]
                for device in devices
                if device.get("site_name")
            }),
            "active_alarms": len(alarms),
            "critical_alarms": sum(
                alarm["severity"] == "critical"
                for alarm in alarms
            ),
            "customers_affected": int(
                uisp.get("summary", {}).get(
                    "customers_affected",
                    0,
                )
                or 0
            ),
            "sources_healthy": sum(
                state == "online" for state in source_states
            ),
            "sources_total": len(source_states),
        },
        "sources": [
            {
                "id": "uisp",
                "name": "UISP NMS",
                "state": uisp_state,
                "mode": "Coalesced device cache",
                "device_count": len(uisp.get("devices", [])),
                "poll_interval_seconds": uisp_cache.get("ttl_seconds"),
                "last_polled_at": uisp_cache.get("loaded_at"),
                "cache_age_seconds": uisp_cache.get("age_seconds"),
                "detail": (
                    errors.get("uisp")
                    or "One upstream read serves all portal consumers."
                ),
            },
            {
                "id": "mikrotik",
                "name": "MikroTik",
                "state": mikrotik_state,
                "mode": "Redis collector cache",
                "device_count": len(mikrotik_routers),
                "poll_interval_seconds": min(
                    [
                        float(row.get("poll_interval_seconds") or 3)
                        for row in mikrotik_routers
                    ]
                    or [settings.mikrotik_poll_interval_seconds]
                ),
                "last_polled_at": max(
                    [
                        str(
                            row.get("last_seen")
                            or row.get("last_attempt_at")
                            or ""
                        )
                        for row in mikrotik_routers
                    ]
                    or [""]
                ) or None,
                "cache_age_seconds": None,
                "detail": (
                    errors.get("mikrotik")
                    or (
                        "Collector disabled by deployment configuration."
                        if not mikrotik_collector_enabled
                        else None
                    )
                    or mikrotik.get("collector", {}).get("detail")
                    or "Centralized RouterOS collector telemetry."
                ),
            },
            {
                "id": "tauc",
                "name": "TAUC",
                "state": tauc_state,
                "mode": "Rate-limited snapshot cache",
                "device_count": len(assignments),
                "poll_interval_seconds": max(
                    1.35,
                    settings.tauc_min_request_interval_seconds,
                ),
                "last_polled_at": max(
                    [
                        str(row.get("generated_at") or "")
                        for row in tauc_cache.values()
                    ]
                    or [""]
                ) or None,
                "cache_age_seconds": min(
                    [
                        float(row.get("cache_age_seconds") or 0)
                        for row in tauc_cache.values()
                    ]
                    or [0]
                ) if tauc_cache else None,
                "cached_devices": len(tauc_cache),
                "detail": (
                    errors.get("tauc")
                    or (
                        "Network reads assignments and fresh snapshots "
                        "without adding TAUC cloud transactions."
                    )
                ),
            },
        ],
        "devices": devices,
        "alarms": alarms,
        "sites": sorted({
            str(device["site_name"])
            for device in devices
            if device.get("site_name")
        }),
        "errors": errors,
    }


@router.get("/overview")
async def get_network_overview(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    try:
        return await overview(limit)
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/devices")
async def get_network_devices(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    try:
        devices = await load_devices(limit)
        return {
            "items": devices,
            "count": len(devices),
            "cache": device_cache_metadata(),
        }
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/devices/{device_id}")
async def get_network_device(
    device_id: str,
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
) -> dict:
    try:
        devices = await load_devices(1000)
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    for device in devices:
        if device["id"] == device_id:
            return device

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Network device not found",
    )


@router.get("/topology")
async def get_network_topology(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
) -> dict:
    try:
        return await topology()
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
