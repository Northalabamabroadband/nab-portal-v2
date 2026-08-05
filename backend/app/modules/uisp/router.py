from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.auth.dependencies import require_permission
from app.modules.uisp.client import UISPClient

router = APIRouter(prefix="/uisp", tags=["uisp"])


@router.get("/status")
async def uisp_status(
    claims: Annotated[
        dict,
        Depends(require_permission("network.read")),
    ],
) -> dict:
    client = UISPClient()
    return await client.connection_status()


@router.get("/clients")
async def search_clients(
    claims: Annotated[
        dict,
        Depends(require_permission("customers.read")),
    ],
    search: str = Query(default="", max_length=160),
    limit: int = Query(default=50, ge=1, le=250),
) -> dict:
    client = UISPClient()
    records = await client.search_clients(search, limit)

    return {
        "items": records,
        "count": len(records),
        "search": search,
    }
