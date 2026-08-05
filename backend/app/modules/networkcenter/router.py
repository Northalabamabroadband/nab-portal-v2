from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.networkcenter.service import load_devices, overview, topology
from app.modules.uisp.client import UISPError

router = APIRouter(prefix="/network-center", tags=["network-center"])


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
        return {"items": devices, "count": len(devices)}
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
