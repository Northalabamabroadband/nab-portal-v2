from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.operations import InventoryItem, SupportTicket, WorkOrder
from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/operations", tags=["operations"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.get("/summary")
def operations_summary(
    claims: Annotated[dict, Depends(require_permission("command_post.view"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    open_tickets = session.scalar(
        select(func.count()).select_from(SupportTicket).where(
            SupportTicket.status.not_in(["resolved", "closed"])
        )
    ) or 0

    active_workorders = session.scalar(
        select(func.count()).select_from(WorkOrder).where(
            WorkOrder.status.not_in(["completed", "cancelled"])
        )
    ) or 0

    low_stock = session.scalar(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.quantity_on_hand <= InventoryItem.reorder_level
        )
    ) or 0

    return {
        "open_tickets": open_tickets,
        "active_workorders": active_workorders,
        "low_stock_items": low_stock,
    }
