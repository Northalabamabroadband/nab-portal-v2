from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.tauc.schemas import GatewayMappingRequest

router = APIRouter(prefix="/customers", tags=["customers", "tauc"])


@router.post("/{client_id}/gateway/resolve")
async def resolve_customer_gateway(
    client_id: str,
    payload: GatewayMappingRequest,
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
) -> dict:
    if payload.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path client ID and payload client ID do not match",
        )

    tauc = TAUCClient()

    try:
        device = await tauc.device_lookup(
            serial_number=payload.serial_number,
            mac_address=payload.mac_address,
        )
        network = await tauc.network_lookup(
            serial_number=payload.serial_number,
            mac_address=payload.mac_address,
        )
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "client_id": client_id,
        "serial_number": payload.serial_number,
        "mac_address": payload.mac_address,
        "device": device,
        "network": network,
        "resolved": True,
    }
