from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.tauc.schemas import DeviceControlRequest, DeviceLookupRequest, WifiSettingRequest

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


@router.get("/devices/{device_id}/snapshot")
async def device_snapshot(
    device_id: str,
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
    network_id: str = Query(default="", max_length=128),
    network_name: str = Query(default="", max_length=256),
) -> dict:
    client = TAUCClient()
    try:
        return await client.gateway_snapshot(
            device_id,
            network_id=network_id,
            network_name=network_name,
        )
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


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


async def _run_control(action):
    try:
        return {"result": await action}
    except TAUCError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/controls/wifi/ssid")
async def set_wifi_ssid(payload: WifiSettingRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(client.set_wifi_ssid(payload.device_id, payload.value))


@router.post("/controls/wifi/password")
async def set_wifi_password(payload: WifiSettingRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(client.set_wifi_password(payload.device_id, payload.value))


@router.post("/controls/reboot")
async def reboot_device(payload: DeviceControlRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(client.reboot(payload.device_id))


@router.post("/controls/diagnostics")
async def run_diagnostics(payload: DeviceControlRequest, claims: Annotated[dict, Depends(require_permission("wifi.read"))]) -> dict:
    client = TAUCClient()
    return await _run_control(client.diagnostics(payload.device_id))
