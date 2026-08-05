from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.fiber import FiberAsset, FiberRoute
from app.modules.auth.dependencies import require_permission
from app.modules.fiber.schemas import (
    FiberAssetCreate,
    FiberAssetRead,
    FiberAssetUpdate,
    FiberRouteCreate,
    FiberRouteRead,
)

router = APIRouter(prefix="/fiber", tags=["fiber"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.get("/assets", response_model=list[FiberAssetRead])
def list_assets(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
    asset_type: str | None = None,
    asset_status: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[FiberAsset]:
    statement = select(FiberAsset).order_by(FiberAsset.asset_type, FiberAsset.name)

    if asset_type:
        statement = statement.where(FiberAsset.asset_type == asset_type)
    if asset_status:
        statement = statement.where(FiberAsset.status == asset_status)
    if search:
        needle = f"%{search.strip()}%"
        statement = statement.where(
            FiberAsset.name.ilike(needle)
            | FiberAsset.asset_code.ilike(needle)
            | FiberAsset.location_name.ilike(needle)
            | FiberAsset.serial_number.ilike(needle)
        )

    return list(session.scalars(statement.limit(limit)).all())


@router.post("/assets", response_model=FiberAssetRead, status_code=201)
def create_asset(
    payload: FiberAssetCreate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> FiberAsset:
    if payload.used_capacity > payload.total_capacity and payload.total_capacity > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Used capacity cannot exceed total capacity",
        )

    asset = FiberAsset(**payload.model_dump())
    session.add(asset)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fiber asset code already exists",
        ) from exc

    session.refresh(asset)
    return asset


@router.patch("/assets/{asset_id}", response_model=FiberAssetRead)
def update_asset(
    asset_id: str,
    payload: FiberAssetUpdate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> FiberAsset:
    asset = session.get(FiberAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Fiber asset not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)

    if asset.total_capacity > 0 and asset.used_capacity > asset.total_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Used capacity cannot exceed total capacity",
        )

    session.commit()
    session.refresh(asset)
    return asset


@router.get("/routes", response_model=list[FiberRouteRead])
def list_routes(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
    route_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[FiberRoute]:
    statement = select(FiberRoute).order_by(FiberRoute.name)
    if route_status:
        statement = statement.where(FiberRoute.status == route_status)
    return list(session.scalars(statement.limit(limit)).all())


@router.post("/routes", response_model=FiberRouteRead, status_code=201)
def create_route(
    payload: FiberRouteCreate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> FiberRoute:
    route = FiberRoute(**payload.model_dump())
    session.add(route)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fiber route code already exists",
        ) from exc

    session.refresh(route)
    return route


@router.get("/summary")
def fiber_summary(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    assets_total = session.scalar(select(func.count()).select_from(FiberAsset)) or 0
    routes_total = session.scalar(select(func.count()).select_from(FiberRoute)) or 0
    onts = session.scalar(
        select(func.count()).select_from(FiberAsset).where(FiberAsset.asset_type == "ont")
    ) or 0
    splitters = session.scalar(
        select(func.count()).select_from(FiberAsset).where(FiberAsset.asset_type == "splitter")
    ) or 0
    damaged = session.scalar(
        select(func.count()).select_from(FiberAsset).where(
            FiberAsset.status.in_(["damaged", "offline", "warning"])
        )
    ) or 0

    capacity = session.execute(
        select(
            func.coalesce(func.sum(FiberAsset.used_capacity), 0),
            func.coalesce(func.sum(FiberAsset.total_capacity), 0),
        )
    ).one()

    used_capacity = int(capacity[0] or 0)
    total_capacity = int(capacity[1] or 0)

    return {
        "assets_total": assets_total,
        "routes_total": routes_total,
        "onts_total": onts,
        "splitters_total": splitters,
        "assets_attention": damaged,
        "used_capacity": used_capacity,
        "total_capacity": total_capacity,
        "available_capacity": max(total_capacity - used_capacity, 0),
        "utilization_percent": round((used_capacity / total_capacity) * 100, 1)
        if total_capacity
        else 0,
    }
