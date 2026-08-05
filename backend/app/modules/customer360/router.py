from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import require_permission
from app.modules.customer360.service import customer_360
from app.modules.uisp.client import UISPError

router = APIRouter(prefix="/customer360", tags=["customer360"])


@router.get("/{client_id}")
async def get_customer_360(
    client_id: str,
    claims: Annotated[
        dict,
        Depends(require_permission("customers.read")),
    ],
) -> dict:
    try:
        return await customer_360(client_id)
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
