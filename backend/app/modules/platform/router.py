from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.observability import OperationalAlert
from app.models.operations import CustomerNote, CustomerTaucAssignment, InventoryItem, SupportTicket, WorkOrder
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import DEFAULT_PERMISSIONS, DEFAULT_ROLES
from app.modules.customer360.service import customer_360
from app.modules.incidents.service import (
    build_incident_command,
    build_outage_events,
    dispatch_resource_id,
    incident_marker,
)
from app.modules.networkcenter.service import overview, topology

router = APIRouter(prefix="/platform", tags=["platform-build018"])


class CustomerNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)



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
    events = build_outage_events(offline)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_outages": len(events),
        "offline_devices": len(offline),
        "customers_affected": sum(x["customers_affected"] for x in events),
        "events": events,
    }



@router.get("/incidents/command")
async def incident_command(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    network = await overview(1000)
    alerts = list(session.scalars(
        select(OperationalAlert)
        .where(OperationalAlert.acknowledged.is_(False))
        .order_by(OperationalAlert.created_at.desc())
        .limit(500)
    ).all())
    tickets = list(session.scalars(
        select(SupportTicket)
        .where(SupportTicket.status.not_in(["resolved", "closed"]))
        .order_by(SupportTicket.created_at.desc())
        .limit(500)
    ).all())
    workorders = list(session.scalars(
        select(WorkOrder)
        .where(WorkOrder.status.not_in(["completed", "cancelled"]))
        .order_by(WorkOrder.created_at.desc())
        .limit(500)
    ).all())
    return build_incident_command(network, alerts, tickets, workorders)



@router.post("/incidents/{incident_id}/dispatch")
async def dispatch_incident(
    incident_id: str,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    network = await overview(1000)
    event = next(
        (row for row in build_outage_events(network.get("alarms", [])) if row["id"] == incident_id),
        None,
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active incident not found",
        )

    marker = incident_marker(incident_id)
    ticket_id = dispatch_resource_id(incident_id, "ticket")
    workorder_id = dispatch_resource_id(incident_id, "workorder")
    actor = str(claims.get("email") or claims.get("sub") or "incident-command")
    priority = "urgent" if event["customers_affected"] >= 25 else "high"
    created: list[str] = []
    reopened: list[str] = []

    ticket = session.get(SupportTicket, ticket_id)
    if ticket is None:
        ticket = SupportTicket(
            id=ticket_id,
            subject=f"Incident response: {event['site_name']}",
            description=(
                f"{marker} Automated Incident Command dispatch for "
                f"{len(event['devices'])} offline device(s) affecting "
                f"{event['customers_affected']} customer(s)."
            ),
            status="open",
            priority=priority,
            created_by=actor,
        )
        session.add(ticket)
        created.append("ticket")
    elif ticket.status in {"resolved", "closed"}:
        ticket.status = "open"
        ticket.priority = priority
        reopened.append("ticket")

    workorder = session.get(WorkOrder, workorder_id)
    if workorder is None:
        workorder = WorkOrder(
            id=workorder_id,
            title=f"Restore service at {event['site_name']}",
            description=(
                f"{marker} Validate power and backhaul, run diagnostics, "
                "and restore the affected network devices."
            ),
            status="open",
            priority=priority,
            service_address=event["site_name"],
            created_by=actor,
        )
        session.add(workorder)
        created.append("workorder")
    elif workorder.status in {"completed", "cancelled"}:
        workorder.status = "open"
        workorder.priority = priority
        reopened.append("workorder")

    session.commit()
    return {
        "incident_id": incident_id,
        "ticket_id": ticket.id,
        "workorder_id": workorder.id,
        "created": created,
        "reopened": reopened,
        "reused": [
            name for name in ("ticket", "workorder")
            if name not in created and name not in reopened
        ],
        "idempotent": not created and not reopened,
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


@router.post("/customers/{client_id}/notes", status_code=201)
def create_customer_note(
    client_id: str,
    payload: CustomerNoteCreate,
    claims: Annotated[dict, Depends(require_permission("customers.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Note cannot be blank")
    note = CustomerNote(
        client_id=client_id,
        body=body,
        author_email=str(claims.get("email") or claims.get("sub") or "unknown"),
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return {
        "id": note.id,
        "client_id": note.client_id,
        "body": note.body,
        "author_email": note.author_email,
        "created_at": note.created_at,
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
    notes = list(session.scalars(
        select(CustomerNote)
        .where(CustomerNote.client_id == client_id)
        .order_by(CustomerNote.created_at.desc())
        .limit(100)
    ).all())
    assignments = list(session.scalars(
        select(CustomerTaucAssignment)
        .where(CustomerTaucAssignment.client_id == client_id)
        .order_by(CustomerTaucAssignment.created_at.asc())
    ).all())
    customer["support"] = {
        "tickets": [{"id": x.id, "subject": x.subject, "status": x.status, "priority": x.priority} for x in tickets],
        "workorders": [{"id": x.id, "title": x.title, "status": x.status, "scheduled_for": x.scheduled_for} for x in orders],
    }
    customer["tauc_devices"] = [assignment.as_dict() for assignment in assignments]
    if assignments:
        primary = assignments[0]
        customer["gateway"] = {
            "source": "customer_assignment",
            "device": {
                "deviceId": primary.tauc_device_id,
                "deviceModel": primary.device_model,
                "sn": primary.serial_number,
                "mac": primary.mac_address,
                "fwVersion": primary.firmware_version,
            },
            "network": {
                "networkId": primary.network_id,
                "networkName": primary.network_name,
            },
        }
        customer.pop("gateway_error", None)
    activity = [
        {
            "id": x.id,
            "kind": "note",
            "title": "Internal account note",
            "detail": x.body,
            "status": "",
            "actor": x.author_email,
            "occurred_at": x.created_at,
        }
        for x in notes
    ]
    activity.extend({
        "id": x.id,
        "kind": "ticket",
        "title": x.subject,
        "detail": f"Support ticket · {x.priority} priority",
        "status": x.status,
        "actor": x.created_by,
        "occurred_at": x.created_at,
    } for x in tickets)
    activity.extend({
        "id": x.id,
        "kind": "workorder",
        "title": x.title,
        "detail": x.service_address or "Field work order",
        "status": x.status,
        "actor": x.created_by,
        "occurred_at": x.created_at,
    } for x in orders)
    activity.extend({
        "id": x.id,
        "kind": "device",
        "title": "TAUC device assigned",
        "detail": f"{x.device_model or 'Gateway'} · SN {x.serial_number}",
        "status": "assigned",
        "actor": x.assigned_by,
        "occurred_at": x.created_at,
    } for x in assignments)
    customer["activity"] = sorted(
        activity,
        key=lambda item: item["occurred_at"],
        reverse=True,
    )[:200]
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



@router.get("/parity")
def capability_parity(
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
) -> dict:
    capabilities = [
        {"domain": "Customer 360", "read": True, "write": True, "source": "UISP CRM + local support"},
        {"domain": "Billing and payments", "read": True, "write": False, "source": "UISP CRM authoritative"},
        {"domain": "Support tickets", "read": True, "write": True, "source": "V2 shared operations"},
        {"domain": "Work orders and dispatch", "read": True, "write": True, "source": "V2 shared operations"},
        {"domain": "Inventory", "read": True, "write": True, "source": "V2 shared operations"},
        {"domain": "Network telemetry", "read": True, "write": False, "source": "UISP NMS authoritative"},
        {"domain": "Outages and incidents", "read": True, "write": True, "source": "UISP NMS + response dispatch"},
        {"domain": "Fiber assets and mapping", "read": True, "write": True, "source": "V2 fiber services"},
        {"domain": "Managed Wi-Fi", "read": True, "write": "configuration-gated", "source": "TAUC"},
        {"domain": "Alerts", "read": True, "write": True, "source": "V2 observability"},
        {"domain": "Roles and audit", "read": True, "write": True, "source": "V2 identity and audit"},
        {"domain": "Customer self-service", "read": "preview", "write": False, "source": "activation controls required"},
    ]
    return {
        "release": "2.0.0-rc1-build018",
        "basis": "Available repository contracts; no external V1 source was present for direct comparison.",
        "capabilities": capabilities,
        "interactive_domains": sum(row["write"] is True for row in capabilities),
        "total_domains": len(capabilities),
        "external_controls": [
            "UISP CRM remains authoritative for billing mutations.",
            "UISP NMS remains authoritative for network configuration.",
            "TAUC writes remain disabled until verified tenant paths are configured.",
            "Customer self-service remains gated on identity recovery and policy controls.",
        ],
    }


@router.get("/admin/capabilities")
def admin_capabilities(
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
) -> dict:
    return {
        "release": "2.0.0-rc1-build018",
        "permissions": DEFAULT_PERMISSIONS,
        "roles": DEFAULT_ROLES,
        "features": {
            "outage_intelligence": True,
            "incident_command": True,
            "incident_dispatch": "idempotent",
            "capability_parity": True,
            "customer_workspace": True,
            "customer_action_center": "permission-and-configuration-gated",
            "tauc_controls": "configuration-gated",
            "crm_workflows": True,
            "network_topology": True,
            "field_operations": True,
            "customer_portal": "admin-preview",
            "reporting": True,
            "role_administration": True,
            "access_control_center": "guarded",
            "customer_activity_timeline": True,
            "tauc_customer_assignments": "durable-and-unique",
        },
    }
