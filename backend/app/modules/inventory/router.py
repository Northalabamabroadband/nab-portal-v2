from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.operations import InventoryItem
from app.modules.auth.dependencies import require_permission
from app.modules.inventory.schemas import InventoryAdjust, InventoryCreate, InventoryRead

router = APIRouter(prefix="/inventory", tags=["inventory"])



@router.get("", response_model=list[InventoryRead])
def list_inventory(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> list[InventoryItem]:
    return list(
        session.scalars(
            select(InventoryItem).order_by(InventoryItem.name)
        ).all()
    )


@router.post("", response_model=InventoryRead, status_code=201)
def create_inventory(
    payload: InventoryCreate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> InventoryItem:
    item = InventoryItem(**payload.model_dump())
    session.add(item)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory SKU already exists",
        ) from exc

    session.refresh(item)
    return item


@router.post("/{item_id}/adjust", response_model=InventoryRead)
def adjust_inventory(
    item_id: str,
    payload: InventoryAdjust,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")

    next_quantity = item.quantity_on_hand + payload.delta
    if next_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory quantity cannot be negative",
        )

    item.quantity_on_hand = next_quantity
    session.commit()
    session.refresh(item)
    return item
