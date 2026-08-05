import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import require_permission
from app.modules.customers.schemas import CustomerSummary
from app.modules.uisp.client import UISPClient, UISPError

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/capabilities")
def customer_capabilities() -> dict[str, object]:
    return {
        "customer_360": True,
        "billing": True,
        "services": True,
        "equipment": True,
        "tickets": True,
        "documents": True,
        "uisp_live_data": True,
        "status": "alpha.4",
    }


@router.get("/{client_id}", response_model=CustomerSummary)
async def customer_summary(
    client_id: str,
    claims: Annotated[
        dict,
        Depends(require_permission("customers.read")),
    ],
) -> CustomerSummary:
    uisp = UISPClient()

    try:
        client, services, invoices, payments = await asyncio.gather(
            uisp.client(client_id),
            uisp.client_services(client_id),
            uisp.client_invoices(client_id),
            uisp.client_payments(client_id),
        )
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CustomerSummary(
        client=client,
        services=services,
        invoices=invoices,
        payments=payments,
        last_payment=payments[0] if payments else None,
    )
