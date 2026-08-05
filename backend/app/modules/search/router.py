from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.auth.dependencies import require_permission
from app.modules.uisp.client import UISPClient

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def global_search(
    claims: Annotated[
        dict,
        Depends(require_permission("customers.read")),
    ],
    q: str = Query(min_length=1, max_length=160),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    uisp = UISPClient()
    clients = await uisp.search_clients(q, limit)

    items = []

    for client in clients:
        name = (
            client.get("companyName")
            or " ".join(
                value
                for value in [
                    str(client.get("firstName") or "").strip(),
                    str(client.get("lastName") or "").strip(),
                ]
                if value
            )
            or client.get("username")
            or "Customer"
        )

        items.append({
            "type": "customer",
            "id": str(client.get("id")),
            "title": name,
            "subtitle": client.get("email") or client.get("username") or "",
            "status": "active" if client.get("isActive", True) else "inactive",
            "raw": client,
        })

    return {
        "query": q,
        "count": len(items),
        "items": items,
    }
