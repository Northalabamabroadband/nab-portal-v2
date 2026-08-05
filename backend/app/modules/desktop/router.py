from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.desktop import DesktopOutage
from app.models.operations import WorkOrder


router = APIRouter(
    prefix="/api/desktop/v1",
    tags=["desktop-sync"],
)


def _configured_api_key() -> str:
    return os.getenv("NAB_DESKTOP_API_KEY", "").strip()


def require_desktop_api_key(
    x_nab_api_key: Annotated[str | None, Header()] = None,
) -> str:
    configured_key = _configured_api_key()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Desktop synchronization API key is not configured.",
        )

    supplied_key = str(x_nab_api_key or "").strip()
    if not supplied_key or not hmac.compare_digest(
        supplied_key.encode("utf-8"),
        configured_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid NAB Command API key.",
        )

    return hashlib.sha256(supplied_key.encode("utf-8")).hexdigest()


class DesktopWorkOrderCreate(BaseModel):
    work_order_number: str = Field(min_length=1, max_length=36)
    job_type: str = Field(default="service_call", max_length=80)
    title: str = Field(min_length=1, max_length=220)
    status: str = Field(default="open", max_length=32)
    priority: str = Field(default="normal", max_length=32)
    customer_name: str = Field(default="Customer", max_length=220)
    customer_phone: str = Field(default="", max_length=80)
    service_address: str = Field(default="", max_length=500)
    scheduled_start: int | None = None
    scheduled_end: int | None = None
    assigned_technician: str = Field(default="", max_length=320)
    description: str = ""


class DesktopOutageCreate(BaseModel):
    external_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=220)
    status: str = Field(default="investigating", max_length=32)
    severity: str = Field(default="warning", max_length=32)
    affected_area: str = Field(default="", max_length=500)
    affected_services: str = Field(
        default="Internet service",
        max_length=500,
    )
    public_message: str = ""
    internal_notes: str = ""
    started_at: int | None = None
    published: bool = True


class DesktopOutageUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    public_message: str | None = None
    published: bool | None = None


def _timestamp(value: datetime | None) -> int:
    if value is None:
        return int(time.time())
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _datetime_from_epoch(value: int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _serialize_work_order(order: WorkOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "work_order_number": order.id,
        "job_type": "service_call",
        "title": order.title,
        "description": order.description or "",
        "status": order.status,
        "priority": order.priority,
        "customer_name": "",
        "customer_phone": "",
        "service_address": order.service_address or "",
        "technician_name": order.assigned_technician or "",
        "technician_email": order.assigned_technician or "",
        "scheduled_start": (
            _timestamp(order.scheduled_for)
            if order.scheduled_for
            else None
        ),
        "created_at": _timestamp(order.created_at),
        "updated_at": _timestamp(order.updated_at),
        "completed_at": None,
    }


def _serialize_outage(outage: DesktopOutage) -> dict[str, Any]:
    return {
        "id": outage.id,
        "external_key": outage.external_key,
        "title": outage.title,
        "status": outage.status,
        "severity": outage.severity,
        "affected_area": outage.affected_area,
        "affected_services": outage.affected_services,
        "public_message": outage.public_message,
        "internal_notes": outage.internal_notes,
        "started_at": (
            _timestamp(outage.started_at)
            if outage.started_at
            else None
        ),
        "published": outage.published,
        "site_name": "",
        "resolved_at": (
            _timestamp(outage.resolved_at)
            if outage.resolved_at
            else None
        ),
        "created_at": _timestamp(outage.created_at),
        "updated_at": _timestamp(outage.updated_at),
    }


@router.get("/health")
def desktop_health(
    api_key_hash: Annotated[str, Depends(require_desktop_api_key)],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "nab-portal-desktop-sync",
        "version": "1.1",
        "server_time": int(time.time()),
        "authenticated": True,
        "key_fingerprint": api_key_hash[:12],
        "outage_storage": "postgresql",
    }


@router.get("/snapshot")
def desktop_snapshot(
    api_key_hash: Annotated[str, Depends(require_desktop_api_key)],
    session: Annotated[Session, Depends(database_session)],
    since: int = Query(default=0, ge=0),
    event_after: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
) -> dict[str, Any]:
    updated_after = _datetime_from_epoch(since) if since else None

    work_statement = select(WorkOrder).order_by(WorkOrder.updated_at.asc())
    outage_statement = select(DesktopOutage).order_by(
        DesktopOutage.updated_at.asc()
    )
    if updated_after is not None:
        work_statement = work_statement.where(
            WorkOrder.updated_at > updated_after
        )
        outage_statement = outage_statement.where(
            DesktopOutage.updated_at > updated_after
        )

    orders = list(session.scalars(work_statement.limit(limit)).all())
    outages = list(session.scalars(outage_statement.limit(limit)).all())

    open_work_orders = session.scalar(
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.status.notin_(
                ["completed", "cancelled", "closed"]
            )
        )
    ) or 0
    active_outages = session.scalar(
        select(func.count())
        .select_from(DesktopOutage)
        .where(DesktopOutage.status.notin_(["resolved", "closed"]))
    ) or 0

    return {
        "server_time": int(time.time()),
        "event_cursor": event_after,
        "technicians": [],
        "work_orders": [
            _serialize_work_order(order)
            for order in orders
        ],
        "outages": [
            _serialize_outage(outage)
            for outage in outages
        ],
        "events": [],
        "summary": {
            "open_work_orders": open_work_orders,
            "active_outages": active_outages,
            "active_technicians": 0,
        },
        "authenticated_key": api_key_hash[:12],
    }


@router.post("/work-orders")
def desktop_create_or_update_work_order(
    payload: DesktopWorkOrderCreate,
    api_key_hash: Annotated[str, Depends(require_desktop_api_key)],
    session: Annotated[Session, Depends(database_session)],
) -> dict[str, Any]:
    order = session.get(WorkOrder, payload.work_order_number)
    scheduled_for = _datetime_from_epoch(payload.scheduled_start)

    if order is None:
        order = WorkOrder(
            id=payload.work_order_number,
            client_id=None,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            assigned_technician=(
                payload.assigned_technician or None
            ),
            service_address=payload.service_address or None,
            scheduled_for=scheduled_for,
            created_by="NAB Command Desktop",
        )
        session.add(order)
    else:
        order.title = payload.title
        order.description = payload.description
        order.status = payload.status
        order.priority = payload.priority
        order.assigned_technician = (
            payload.assigned_technician or None
        )
        order.service_address = payload.service_address or None
        order.scheduled_for = scheduled_for

    session.commit()
    session.refresh(order)

    return {
        "work_order": _serialize_work_order(order),
        "authenticated_key": api_key_hash[:12],
    }


@router.post("/outages", status_code=201)
def desktop_create_outage(
    payload: DesktopOutageCreate,
    api_key_hash: Annotated[str, Depends(require_desktop_api_key)],
    session: Annotated[Session, Depends(database_session)],
) -> dict[str, Any]:
    outage = session.scalar(
        select(DesktopOutage).where(
            DesktopOutage.external_key == payload.external_key
        )
    )
    started_at = _datetime_from_epoch(payload.started_at)

    if outage is None:
        outage = DesktopOutage(
            external_key=payload.external_key,
            title=payload.title,
            status=payload.status,
            severity=payload.severity,
            affected_area=payload.affected_area,
            affected_services=payload.affected_services,
            public_message=payload.public_message,
            internal_notes=payload.internal_notes,
            started_at=started_at,
            published=payload.published,
        )
        session.add(outage)
    else:
        outage.title = payload.title
        outage.status = payload.status
        outage.severity = payload.severity
        outage.affected_area = payload.affected_area
        outage.affected_services = payload.affected_services
        outage.public_message = payload.public_message
        outage.internal_notes = payload.internal_notes
        outage.started_at = started_at
        outage.published = payload.published

    if outage.status.lower() in {"resolved", "closed"}:
        outage.resolved_at = datetime.now(timezone.utc)
    else:
        outage.resolved_at = None

    session.commit()
    session.refresh(outage)

    return {
        "outage": _serialize_outage(outage),
        "authenticated_key": api_key_hash[:12],
    }


@router.patch("/outages/{outage_id}")
def desktop_update_outage(
    outage_id: int,
    payload: DesktopOutageUpdate,
    api_key_hash: Annotated[str, Depends(require_desktop_api_key)],
    session: Annotated[Session, Depends(database_session)],
) -> dict[str, Any]:
    outage = session.get(DesktopOutage, outage_id)
    if outage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outage not found.",
        )

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(outage, field, value)

    if outage.status.lower() in {"resolved", "closed"}:
        outage.resolved_at = outage.resolved_at or datetime.now(timezone.utc)
    else:
        outage.resolved_at = None

    session.commit()
    session.refresh(outage)

    return {
        "outage": _serialize_outage(outage),
        "authenticated_key": api_key_hash[:12],
    }
