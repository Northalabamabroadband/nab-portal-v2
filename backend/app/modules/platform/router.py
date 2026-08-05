from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.operations import InventoryItem, SupportTicket, WorkOrder
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import DEFAULT_PERMISSIONS, DEFAULT_ROLES
from app.modules.customer360.service import customer_360
from app.modules.networkcenter.service import overview, topology

router = APIRouter(prefix="/platform", tags=["platform-build005"])



@router.get("/outages")
async def outage_intelligence(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    limit: int = Query(default=1000, ge=1, le=2000),
) -> dict:
    network = await overview(limit)
    offline = [
        alarm for alarm in network["alarms"]
        if alarm["type"] == "device_offline"
    ]
    sites: dict[str, dict] = {}
    for alarm in offline:
        site = sites.setdefault(alarm["site_name"], {
            "site_name": alarm["site_name"],
            "devices": [],
            "customers_affected": 0,
            "severity": "critical",
        })
        site["devices"].append({
            "id": alarm["device_id"],
            "name": alarm["device_name"],
        })
        site["customers_affected"] += alarm["customers_affected"]

    events = sorted(
        sites.values(),
        key=lambda row: row["customers_affected"],
        reverse=True,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_outages": len(events),
        "offline_devices": len(offline),
        "customers_affected": sum(x["customers_affected"] for x in events),
        "events": events,
    }


@router.get("/network-intelligence")
async def network_intelligence(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
) -> dict:
    network = await overview(1000)
    graph = await topology(1000)
    models = Counter(device["model"] for device in network["devices"])
    return {
        "summary": network["summary"],
        "topology": graph,
        "performance": {
            "devices_reporting_cpu": sum(d["cpu"] is not None for d in network["devices"]),
            "devices_reporting_signal": sum(d["signal"] is not None for d in network["devices"]),
            "average_latency_ms": _average(d["latency"] for d in network["devices"]),
            "average_packet_loss": _average(d["packet_loss"] for d in network["devices"]),
            "average_cpu": _average(d["cpu"] for d in network["devices"]),
            "average_memory": _average(d["memory"] for d in network["devices"]),
        },
        "fleet_models": [
            {"model": model, "count": count}
            for model, count in models.most_common()
        ],
    }


def _average(values) -> float | None:
    rows = [float(value) for value in values if value is not None]
    return round(sum(rows) / len(rows), 2) if rows else None


@router.get("/field/my-work")
def field_queue(
    claims: Annotated[dict, Depends(require_permission("field.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    email = str(claims.get("email") or "")
    statement = (
        select(WorkOrder)
        .where(WorkOrder.status.not_in(["completed", "cancelled"]))
        .order_by(WorkOrder.scheduled_for.asc(), WorkOrder.created_at.desc())
    )
    if "super_admin" not in claims.get("roles", []):
        statement = statement.where(WorkOrder.assigned_technician == email)
    rows = list(session.scalars(statement.limit(250)).all())
    return {
        "technician": email,
        "count": len(rows),
        "items": [
            {
                "id": row.id,
                "client_id": row.client_id,
                "title": row.title,
                "description": row.description,
                "status": row.status,
                "priority": row.priority,
                "service_address": row.service_address,
                "scheduled_for": row.scheduled_for,
                "assigned_technician": row.assigned_technician,
            }
            for row in rows
        ],
    }


@router.get("/reports/operations")
def operations_report(
    claims: Annotated[dict, Depends(require_permission("reports.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    ticket_status = dict(session.execute(
        select(SupportTicket.status, func.count()).group_by(SupportTicket.status)
    ).all())
    work_status = dict(session.execute(
        select(WorkOrder.status, func.count()).group_by(WorkOrder.status)
    ).all())
    low_stock = session.scalar(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.quantity_on_hand <= InventoryItem.reorder_level
        )
    ) or 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickets_by_status": ticket_status,
        "workorders_by_status": work_status,
        "low_stock_items": low_stock,
        "open_tickets": sum(v for k, v in ticket_status.items() if k not in {"closed", "resolved"}),
        "active_workorders": sum(v for k, v in work_status.items() if k not in {"completed", "cancelled"}),
    }


@router.get("/customers/{client_id}/workspace")
async def customer_workspace(
    client_id: str,
    claims: Annotated[dict, Depends(require_permission("customers.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    customer = await customer_360(client_id)
    tickets = list(session.scalars(
        select(SupportTicket)
        .where(SupportTicket.client_id == client_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(100)
    ).all())
    orders = list(session.scalars(
        select(WorkOrder)
        .where(WorkOrder.client_id == client_id)
        .order_by(WorkOrder.created_at.desc())
        .limit(100)
    ).all())
    customer["support"] = {
        "tickets": [{"id": x.id, "subject": x.subject, "status": x.status, "priority": x.priority} for x in tickets],
        "workorders": [{"id": x.id, "title": x.title, "status": x.status, "scheduled_for": x.scheduled_for} for x in orders],
    }
    return customer


@router.get("/portal/readiness")
def customer_portal_readiness(
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
) -> dict:
    return {
        "enabled": False,
        "mode": "admin-preview",
        "requirements": [
            "customer identity verification provider",
            "email or SMS recovery channel",
            "rate limiting and account lockout policy",
            "customer-facing terms and privacy policy",
        ],
        "available_data": ["profile", "balance", "invoices", "payments", "services", "tickets", "workorders", "gateway"],
    }


@router.get("/admin/capabilities")
def admin_capabilities(
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
) -> dict:
    return {
        "release": "2.0.0-rc1-build005",
        "permissions": DEFAULT_PERMISSIONS,
        "roles": DEFAULT_ROLES,
        "features": {
            "outage_intelligence": True,
            "customer_workspace": True,
            "tauc_controls": "configuration-gated",
            "crm_workflows": True,
            "network_topology": True,
            "field_operations": True,
            "customer_portal": "admin-preview",
            "reporting": True,
            "role_administration": True,
        },
    }
