from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.modules.auth.dependencies import require_permission
from app.modules.live.manager import manager
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

    uisp_status = await uisp.connection_status()
    tauc_status = await tauc.connection_status()

    return {
        "status": (
            "operational"
            if uisp_status.get("connected")
            else "degraded"
        ),
        "uisp": uisp_status,
        "tauc": tauc_status,
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
