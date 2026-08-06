from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.mikrotik.client import MikroTikClient

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
                f"{MAX_THROUGHPUT_INTERFACES} interfaces per live poll."
            ),
        )

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
