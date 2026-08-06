import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.modules.auth.dependencies import require_permission
from app.modules.live.manager import manager
from app.modules.mikrotik.collector import collector
from app.modules.tauc.client import TAUCClient
from app.modules.uisp.client import UISPClient

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/summary")
async def live_summary(
    claims: Annotated[
        dict,
        Depends(require_permission("command_post.view")),
    ],
) -> dict:
    uisp = UISPClient()
    tauc = TAUCClient()
    uisp_status, tauc_status, mikrotik_fleet = await asyncio.gather(
        uisp.connection_status(),
        tauc.connection_status(),
        collector.fleet_status(),
    )
    routers = mikrotik_fleet.get("routers", [])
    configured_routers = [row for row in routers if row.get("configured")]
    connected_routers = [row for row in routers if row.get("connected")]
    mikrotik_status = {
        "service": "mikrotik",
        "configured": bool(configured_routers),
        "connected": bool(connected_routers),
        "identity": (
            f"{len(connected_routers)} of {len(configured_routers)} routers live"
            if configured_routers
            else None
        ),
        "detail": mikrotik_fleet.get("collector", {}).get("detail"),
        "collector": mikrotik_fleet.get("collector", {}),
        "routers": routers,
    }

    return {
        "status": (
            "operational"
            if (
                uisp_status.get("connected")
                and (
                    not mikrotik_status.get("configured")
                    or mikrotik_status.get("connected")
                )
            )
            else "degraded"
        ),
        "uisp": uisp_status,
        "tauc": tauc_status,
        "mikrotik": mikrotik_status,
        "active_outages": 0,
        "customers_affected": 0,
        "open_tickets": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.websocket("/ws")
async def live_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "NAB COMMAND POST live channel connected",
        })

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
