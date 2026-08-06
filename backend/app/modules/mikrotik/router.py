from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.auth.dependencies import require_permission
from app.modules.mikrotik.client import MikroTikClient

router = APIRouter(prefix="/mikrotik", tags=["mikrotik-routeros"])


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
