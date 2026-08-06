import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.core.settings import get_settings
from app.models.operations import CustomerTaucAssignment
from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.tauc.schemas import DeviceControlRequest, DeviceLookupRequest, WifiSettingRequest

router = APIRouter(prefix="/tauc", tags=["tauc"])
settings = get_settings()
_TAUC_SNAPSHOT_LOCK = asyncio.Lock()
_TAUC_SNAPSHOT_TASKS: dict[str, asyncio.Task[dict]] = {}
_TAUC_SNAPSHOT_CACHE: dict[str, tuple[float, dict]] = {}
WPA_HEX_KEY = re.compile(r"^[0-9a-fA-F]{64}$")


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


async def invalidate_snapshot_cache(device_id: str) -> None:
    prefix = device_id.strip() + "|"
    async with _TAUC_SNAPSHOT_LOCK:
        for key in [
            cached_key
            for cached_key in _TAUC_SNAPSHOT_CACHE
            if cached_key.startswith(prefix)
        ]:
            _TAUC_SNAPSHOT_CACHE.pop(key, None)


async def cached_snapshot_polling_status() -> dict[str, dict]:
    now = time.monotonic()
    statuses: dict[str, dict] = {}
    async with _TAUC_SNAPSHOT_LOCK:
        expired: list[str] = []
        for key, (expires_at, snapshot) in _TAUC_SNAPSHOT_CACHE.items():
            if expires_at <= now:
                expired.append(key)
                continue
            device_id = key.split("|", 1)[0]
            current = statuses.get(device_id)
            remaining = max(0.0, expires_at - now)
            if current and current["cache_remaining_seconds"] >= remaining:
                continue
            connected_devices = snapshot.get("connected_devices", [])
            wifi_networks = snapshot.get("wifi_networks", [])
            warnings = snapshot.get("warnings", [])
            cache_age = max(
                0.0,
                settings.tauc_snapshot_cache_seconds - remaining,
            )
            statuses[device_id] = {
                "status": str(snapshot.get("status") or "ready"),
                "network_id": snapshot.get("network_id"),
                "network_name": snapshot.get("network_name"),
                "connected_devices": (
                    len(connected_devices)
                    if isinstance(connected_devices, list)
                    else 0
                ),
                "wifi_networks": (
                    len(wifi_networks)
                    if isinstance(wifi_networks, list)
                    else 0
                ),
                "warning_count": (
                    len(warnings) if isinstance(warnings, list) else 0
                ),
                "generated_at": (
                    snapshot.get("generated_at")
                    or (
                        datetime.now(timezone.utc)
                        - timedelta(seconds=cache_age)
                    ).isoformat()
                ),
                "cache_age_seconds": round(cache_age, 2),
                "cache_remaining_seconds": round(remaining, 2),
            }
        for key in expired:
            _TAUC_SNAPSHOT_CACHE.pop(key, None)
    return statuses


def validate_ssid(value: str) -> str:
    ssid = value.strip()
    if not ssid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Wi-Fi name cannot be blank",
        )
    if len(ssid.encode("utf-8")) > 32:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Wi-Fi name must be no more than 32 UTF-8 bytes",
        )
    return ssid


def validate_wifi_password(value: str) -> str:
    if WPA_HEX_KEY.fullmatch(value):
        return value
    password_bytes = len(value.encode("utf-8"))
    if 8 <= password_bytes <= 63:
        return value
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "Wi-Fi password must contain 8–63 characters, or exactly "
            "64 hexadecimal characters"
        ),
    )


@router.get("/fleet")
def managed_wifi_fleet(
    claims: Annotated[
        dict,
        Depends(require_permission("wifi.read")),
    ],
    session: Annotated[Session, Depends(database_session)],
    limit: int = Query(default=1000, ge=1, le=2000),
) -> dict:
    assignments = list(session.scalars(
        select(CustomerTaucAssignment)
        .order_by(
            CustomerTaucAssignment.network_name.asc(),
            CustomerTaucAssignment.created_at.desc(),
        )
        .limit(limit)
    ).all())
    integration = TAUCClient().configuration_status()
    controls = integration.get("controls", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integration": integration,
        "summary": {
            "assigned_gateways": len(assignments),
            "managed_customers": len({
                assignment.client_id for assignment in assignments
            }),
            "known_networks": len({
                assignment.network_id
                for assignment in assignments
                if assignment.network_id
            }),
            "write_controls_ready": sum(
                bool(value)
                for key, value in controls.items()
                if key != "provider_diagnostics"
            ),
        },
        "items": [assignment.as_dict() for assignment in assignments],
    }


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


async def _run_control(
    action,
    *,
    device_id: str,
    action_name: str,
):
    try:
        await action
        await invalidate_snapshot_cache(device_id)
        return {
            "ok": True,
            "action": action_name,
            "device_id": device_id,
        }
    except TAUCError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/controls/wifi/ssid")
async def set_wifi_ssid(payload: WifiSettingRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(
        client.set_wifi_ssid(
            payload.device_id,
            validate_ssid(payload.value),
            payload.network_id or "",
        ),
        device_id=payload.device_id,
        action_name="wifi.ssid.update",
    )


@router.post("/controls/wifi/password")
async def set_wifi_password(payload: WifiSettingRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(
        client.set_wifi_password(
            payload.device_id,
            validate_wifi_password(payload.value),
            payload.network_id or "",
        ),
        device_id=payload.device_id,
        action_name="wifi.password.update",
    )


@router.post("/controls/reboot")
async def reboot_device(payload: DeviceControlRequest, claims: Annotated[dict, Depends(require_permission("wifi.write"))]) -> dict:
    client = TAUCClient()
    return await _run_control(
        client.reboot(payload.device_id, payload.network_id or ""),
        device_id=payload.device_id,
        action_name="gateway.reboot",
    )


@router.post("/controls/diagnostics")
async def run_diagnostics(payload: DeviceControlRequest, claims: Annotated[dict, Depends(require_permission("wifi.read"))]) -> dict:
    client = TAUCClient()
    try:
        return {
            "result": await client.diagnostics(
                payload.device_id,
                network_id=payload.network_id or "",
                network_name=payload.network_name or "",
                serial_number=payload.serial_number or "",
                mac_address=payload.mac_address or "",
            )
        }
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
