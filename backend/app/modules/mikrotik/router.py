from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.mikrotik.client import (
    MikroTikClient,
    MikroTikError,
    router_profile,
)
from app.modules.mikrotik.collector import collector

router = APIRouter(prefix="/mikrotik", tags=["mikrotik-routeros"])

MAX_THROUGHPUT_INTERFACES = 6


def _counter(value: Any) -> int:
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def interface_throughput_sample(
    rows: list[dict[str, Any]],
    selected_names: list[str],
) -> dict[str, Any]:
    by_name = {
        str(row.get("name") or "").strip(): row
        for row in rows
        if str(row.get("name") or "").strip()
    }
    names = selected_names or list(by_name)
    interfaces = []
    for name in names:
        row = by_name.get(name)
        if row is None:
            continue
        interfaces.append({
            "id": str(row.get(".id") or name),
            "name": name,
            "running": str(row.get("running", "")).lower() == "true",
            "disabled": str(row.get("disabled", "")).lower() == "true",
            "rx_bytes": _counter(row.get("rx-byte")),
            "tx_bytes": _counter(row.get("tx-byte")),
        })
    return {
        "interfaces": interfaces,
        "missing": [name for name in names if name not in by_name],
    }


def _profile_or_404(router_key: str):
    try:
        return router_profile(router_key)
    except MikroTikError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


def _selected_interfaces(interface: list[str] | None) -> list[str]:
    selected_names = list(dict.fromkeys(
        name.strip()
        for name in (interface or [])
        if name.strip()
    ))
    if len(selected_names) > MAX_THROUGHPUT_INTERFACES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Select no more than "
                f"{MAX_THROUGHPUT_INTERFACES} interfaces per request."
            ),
        )
    return selected_names


@router.get("/fleet")
async def mikrotik_fleet(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    try:
        return await collector.fleet_status()
    except MikroTikError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/routers/{router_key}/status")
async def mikrotik_router_status(
    router_key: str,
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    return await MikroTikClient(_profile_or_404(router_key)).connection_status()


@router.get("/routers/{router_key}/snapshot")
async def mikrotik_router_snapshot(
    router_key: str,
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    return await MikroTikClient(_profile_or_404(router_key)).snapshot()


@router.get("/routers/{router_key}/history")
async def mikrotik_router_history(
    router_key: str,
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    interface: list[str] | None = Query(default=None),
    minutes: int = Query(default=10, ge=1, le=10080),
) -> dict:
    profile = _profile_or_404(router_key)
    selected_names = _selected_interfaces(interface)
    try:
        samples = await collector.live_history(profile.key, selected_names)
        rollups = (
            await collector.rollup_history(profile.key, minutes, selected_names)
            if minutes > 10
            else []
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MikroTik collector history unavailable: {exc}",
        ) from exc
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "router_key": profile.key,
        "poll_interval_seconds": profile.poll_interval_seconds,
        "mode": "centralized-collector-cache",
        "samples": samples,
        "rollups": rollups,
        "retention_minutes": minutes,
    }


@router.get("/status")
async def mikrotik_status(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    return await MikroTikClient().connection_status()


@router.get("/snapshot")
async def mikrotik_snapshot(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    return await MikroTikClient().snapshot()


@router.get("/interfaces")
async def mikrotik_interfaces(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    rows = await MikroTikClient().records("/interface")
    return {"count": len(rows[:limit]), "items": rows[:limit]}


@router.get("/throughput")
async def mikrotik_throughput(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    interface: list[str] | None = Query(default=None),
) -> dict:
    selected_names = _selected_interfaces(interface)

    sample = interface_throughput_sample(
        await MikroTikClient().records("/interface"),
        selected_names,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "poll_interval_seconds": 3,
        "mode": "read-only-counter-sampling",
        "count": len(sample["interfaces"]),
        **sample,
    }


@router.get("/dhcp-leases")
async def mikrotik_dhcp_leases(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    limit: int = Query(default=1000, ge=1, le=2000),
) -> dict:
    rows = await MikroTikClient().records("/ip/dhcp-server/lease")
    return {"count": len(rows[:limit]), "items": rows[:limit]}


@router.get("/arp")
async def mikrotik_arp(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    limit: int = Query(default=1000, ge=1, le=2000),
) -> dict:
    rows = await MikroTikClient().records("/ip/arp")
    return {"count": len(rows[:limit]), "items": rows[:limit]}
