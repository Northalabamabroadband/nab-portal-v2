from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.fiber import FiberAsset, FiberRoute
from app.models.fiber_map import FiberRouteGeometry
from app.modules.auth.dependencies import require_permission
from app.modules.fibermap.schemas import RouteGeometryWrite

router = APIRouter(prefix="/fiber-map", tags=["fiber-map"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def asset_feature(asset: FiberAsset) -> dict:
    return {
        "type": "Feature",
        "id": asset.id,
        "geometry": {
            "type": "Point",
            "coordinates": [asset.longitude, asset.latitude],
        },
        "properties": {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "name": asset.name,
            "asset_code": asset.asset_code,
            "status": asset.status,
            "location_name": asset.location_name,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "client_id": asset.client_id,
            "used_capacity": asset.used_capacity,
            "total_capacity": asset.total_capacity,
        },
    }


@router.get("")
def get_fiber_map(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    assets = list(
        session.scalars(
            select(FiberAsset).where(
                FiberAsset.latitude.is_not(None),
                FiberAsset.longitude.is_not(None),
                FiberAsset.retired.is_(False),
            )
        ).all()
    )

    all_asset_count = session.query(FiberAsset).filter(
        FiberAsset.retired.is_(False)
    ).count()

    routes = list(session.scalars(select(FiberRoute)).all())
    geometries = {
        geometry.route_id: geometry
        for geometry in session.scalars(select(FiberRouteGeometry)).all()
    }

    route_features: list[dict] = []
    routes_without_geometry: list[dict] = []

    for route in routes:
        geometry = geometries.get(route.id)

        if geometry is None:
            routes_without_geometry.append({
                "id": route.id,
                "route_code": route.route_code,
                "name": route.name,
                "status": route.status,
            })
            continue

        try:
            parsed_geometry = json.loads(geometry.geometry_geojson)
        except (TypeError, ValueError):
            continue

        route_features.append({
            "type": "Feature",
            "id": route.id,
            "geometry": parsed_geometry,
            "properties": {
                "id": route.id,
                "route_code": route.route_code,
                "name": route.name,
                "status": route.status,
                "cable_type": route.cable_type,
                "strand_count": route.strand_count,
                "length_feet": route.length_feet,
                "start_location": route.start_location,
                "end_location": route.end_location,
                "ownership": route.ownership,
                "source": geometry.source,
                "updated_at": geometry.updated_at.isoformat()
                if geometry.updated_at
                else None,
            },
        })

    return {
        "assets": {
            "type": "FeatureCollection",
            "features": [asset_feature(asset) for asset in assets],
        },
        "routes": {
            "type": "FeatureCollection",
            "features": route_features,
        },
        "summary": {
            "mapped_assets": len(assets),
            "unmapped_assets": max(all_asset_count - len(assets), 0),
            "mapped_routes": len(route_features),
            "unmapped_routes": len(routes_without_geometry),
        },
        "routes_without_geometry": routes_without_geometry,
    }


@router.put("/routes/{route_id}/geometry")
def save_route_geometry(
    route_id: str,
    payload: RouteGeometryWrite,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    route = session.get(FiberRoute, route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fiber route not found",
        )

    geometry = session.scalar(
        select(FiberRouteGeometry).where(
            FiberRouteGeometry.route_id == route_id
        )
    )

    if geometry is None:
        geometry = FiberRouteGeometry(route_id=route_id)
        session.add(geometry)

    geometry.geometry_geojson = json.dumps(
        payload.geometry,
        separators=(",", ":"),
    )
    geometry.source = payload.source
    geometry.updated_by = str(claims.get("email") or "unknown")

    session.commit()
    session.refresh(geometry)

    return {
        "route_id": route_id,
        "geometry": payload.geometry,
        "source": geometry.source,
        "updated_by": geometry.updated_by,
        "updated_at": geometry.updated_at,
    }


@router.delete("/routes/{route_id}/geometry", status_code=204)
def delete_route_geometry(
    route_id: str,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
):
    geometry = session.scalar(
        select(FiberRouteGeometry).where(
            FiberRouteGeometry.route_id == route_id
        )
    )

    if geometry is not None:
        session.delete(geometry)
        session.commit()

    return None
