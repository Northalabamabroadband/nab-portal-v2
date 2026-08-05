from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.billingcenter.service import billing_summary
from app.modules.uisp.client import UISPError

router = APIRouter(prefix="/billing-center", tags=["billing-center"])


@router.get("/summary")
async def get_billing_summary(
    claims: Annotated[
        dict,
        Depends(require_permission("billing.read")),
    ],
    limit: int = Query(default=250, ge=1, le=250),
) -> dict:
    try:
        return await billing_summary(limit)
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
