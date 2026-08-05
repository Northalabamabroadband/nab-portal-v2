from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.tauc.schemas import DeviceLookupRequest

router = APIRouter(prefix="/tauc", tags=["tauc"])


@router.get("/status")
async def tauc_status(
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
) -> dict:
    client = TAUCClient()
    return await client.connection_status()


@router.post("/devices/lookup")
async def device_lookup(
    payload: DeviceLookupRequest,
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
) -> dict:
    client = TAUCClient()

    try:
        result = await client.device_lookup(
            serial_number=payload.serial_number,
            mac_address=payload.mac_address,
        )
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"device": result}


@router.post("/networks/lookup")
async def network_lookup(
    payload: DeviceLookupRequest,
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
) -> dict:
    client = TAUCClient()

    try:
        result = await client.network_lookup(
            serial_number=payload.serial_number,
            mac_address=payload.mac_address,
        )
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"network": result}
