from __future__ import annotations

import asyncio

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.settings import get_settings
from app.modules.auth.dependencies import require_permission
from app.modules.mikrotik.client import MikroTikClient
from app.modules.tauc.client import TAUCClient
from app.modules.uisp.client import UISPClient

router = APIRouter(prefix="/integrations", tags=["integrations"])
settings = get_settings()


@router.get("/health")
async def integration_health(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
) -> dict:
    crm = UISPClient("crm")
    nms = UISPClient("nms")
    tauc = TAUCClient()
    mikrotik = MikroTikClient()

    crm_status, nms_status, tauc_status, mikrotik_status = await asyncio.gather(
        crm.connection_status(),
        nms.connection_status(),
        tauc.connection_status(),
        mikrotik.connection_status(),
    )

    return {
        "uisp_crm": crm_status,
        "uisp_nms": nms_status,
        "tauc": tauc_status,
        "mikrotik": mikrotik_status,
        "configuration": {
            "crm_clients_path": settings.uisp_crm_clients_path,
            "mikrotik_mode": "read-only",
            "mikrotik_tls_verification": settings.mikrotik_verify_tls,
            "mikrotik_ca_certificate_configured": bool(settings.mikrotik_ca_cert),
            "nms_devices_path_override": (
                settings.uisp_nms_devices_path or None
            ),
            "tauc_device_lookup_path": getattr(settings, "tauc_device_lookup_path", "/v1/openapi/device-information/device-id"),
            "tauc_network_lookup_path": getattr(settings, "tauc_network_lookup_path", "/v1/openapi/device-information/device-info"),
        },
    }
