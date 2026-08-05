import asyncio
from copy import deepcopy
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.settings import get_settings
from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.tauc.schemas import DeviceControlRequest, DeviceLookupRequest, WifiSettingRequest

router = APIRouter(prefix="/tauc", tags=["tauc"])
settings = get_settings()
_TAUC_SNAPSHOT_LOCK = asyncio.Lock()
_TAUC_SNAPSHOT_TASKS: dict[str, asyncio.Task[dict]] = {}
_TAUC_SNAPSHOT_CACHE: dict[str, tuple[float, dict]] = {}


def snapshot_cache_key(
    device_id: str,
    network_id: str,
    network_name: str,
    serial_number: str,
    mac_address: str,
) -> str:
    return "|".join((
        device_id.strip(),
        network_id.strip(),
        network_name.strip().casefold(),
        serial_number.strip().casefold(),
        mac_address.strip().replace(":", "").replace("-", "").upper(),
    ))


def cacheable_snapshot(snapshot: dict) -> bool:
    warnings = " ".join(
        str(warning) for warning in snapshot.get("warnings", [])
    ).casefold()
    return bool(snapshot.get("network_id")) and all(
        marker not in warnings
        for marker in ("-70307", "rate limit", "visit count")
    )


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
    serial_number: str = Query(default="", max_length=128),
    mac_address: str = Query(default="", max_length=64),
) -> dict:
    key = snapshot_cache_key(
        device_id,
        network_id,
        network_name,
        serial_number,
        mac_address,
    )
    async with _TAUC_SNAPSHOT_LOCK:
        cached = _TAUC_SNAPSHOT_CACHE.get(key)
        if cached and cached[0] > time.monotonic():
            return deepcopy(cached[1])
        if cached:
            _TAUC_SNAPSHOT_CACHE.pop(key, None)
        task = _TAUC_SNAPSHOT_TASKS.get(key)
        if task is None:
            client = TAUCClient()
            task = asyncio.create_task(client.gateway_snapshot(
                device_id,
                network_id=network_id,
                network_name=network_name,
                serial_number=serial_number,
                mac_address=mac_address,
            ))
            _TAUC_SNAPSHOT_TASKS[key] = task

    try:
        snapshot = await task
    except TAUCError as exc:
        async with _TAUC_SNAPSHOT_LOCK:
            if _TAUC_SNAPSHOT_TASKS.get(key) is task:
                _TAUC_SNAPSHOT_TASKS.pop(key, None)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        async with _TAUC_SNAPSHOT_LOCK:
            if _TAUC_SNAPSHOT_TASKS.get(key) is task:
                _TAUC_SNAPSHOT_TASKS.pop(key, None)
        raise

    async with _TAUC_SNAPSHOT_LOCK:
        if _TAUC_SNAPSHOT_TASKS.get(key) is task:
            _TAUC_SNAPSHOT_TASKS.pop(key, None)
        if cacheable_snapshot(snapshot):
            _TAUC_SNAPSHOT_CACHE[key] = (
                time.monotonic() + settings.tauc_snapshot_cache_seconds,
                deepcopy(snapshot),
            )
    return deepcopy(snapshot)


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
