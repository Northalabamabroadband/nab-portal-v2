from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.operations import WorkOrder
from app.modules.auth.dependencies import require_permission
from app.modules.workorders.schemas import WorkOrderCreate, WorkOrderRead, WorkOrderUpdate

router = APIRouter(prefix="/workorders", tags=["workorders"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.get("", response_model=list[WorkOrderRead])
def list_workorders(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
    work_status: str | None = Query(default=None, alias="status"),
    technician: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[WorkOrder]:
    statement = select(WorkOrder).order_by(WorkOrder.created_at.desc())

    if work_status:
        statement = statement.where(WorkOrder.status == work_status)

    if technician:
        statement = statement.where(WorkOrder.assigned_technician == technician)

    return list(session.scalars(statement.limit(limit)).all())


@router.post("", response_model=WorkOrderRead, status_code=201)
def create_workorder(
    payload: WorkOrderCreate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> WorkOrder:
    order = WorkOrder(
        **payload.model_dump(),
        created_by=str(claims.get("email") or "unknown"),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.patch("/{order_id}", response_model=WorkOrderRead)
def update_workorder(
    order_id: str,
    payload: WorkOrderUpdate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> WorkOrder:
    order = session.get(WorkOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, field, value)

    session.commit()
    session.refresh(order)
    return order
