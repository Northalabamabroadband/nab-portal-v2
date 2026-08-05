from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any


def build_outage_events(alarms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    sites: dict[str, dict[str, Any]] = {}
    for alarm in alarms:
        if alarm.get("type") != "device_offline":
            continue
        site_name = str(alarm.get("site_name") or "Unknown site")
        site = sites.setdefault(site_name, {
            "id": _slug(site_name),
            "site_name": site_name,
            "devices": [],
            "customers_affected": 0,
            "severity": "critical",
        })
        site["devices"].append({
            "id": alarm.get("device_id"),
            "name": alarm.get("device_name") or "Unknown device",
        })
        site["customers_affected"] += int(alarm.get("customers_affected") or 0)

    return sorted(
        sites.values(),
        key=lambda row: (row["customers_affected"], len(row["devices"])),
        reverse=True,
    )


def build_incident_command(
    network: dict[str, Any],
    alerts: Iterable[Any],
    tickets: Iterable[Any],
    workorders: Iterable[Any],
) -> dict[str, Any]:
    events = build_outage_events(network.get("alarms", []))
    alert_rows = list(alerts)
    ticket_rows = list(tickets)
    workorder_rows = list(workorders)
    alert_by_resource: dict[str, list[Any]] = {}
    for alert in alert_rows:
        resource_id = str(getattr(alert, "resource_id", "") or "")
        if resource_id:
            alert_by_resource.setdefault(resource_id, []).append(alert)

    incidents = []
    for event in events:
        device_ids = {str(device.get("id")) for device in event["devices"] if device.get("id")}
        related_alerts = [
            alert
            for device_id in device_ids
            for alert in alert_by_resource.get(device_id, [])
        ]
        customer_impact = event["customers_affected"]
        severity = "critical" if customer_impact >= 25 else "major" if customer_impact else "warning"
        incidents.append({
            **event,
            "severity": severity,
            "alert_count": len(related_alerts),
            "phase": "active",
            "recommended_action": _recommendation(customer_impact, len(event["devices"])),
        })

    unassigned_work = sum(
        not getattr(order, "assigned_technician", None)
        for order in workorder_rows
    )
    urgent_tickets = sum(
        str(getattr(ticket, "priority", "")).lower() in {"urgent", "critical", "high"}
        for ticket in ticket_rows
    )
    critical_alerts = sum(
        str(getattr(alert, "severity", "")).lower() == "critical"
        for alert in alert_rows
    )
    affected = sum(event["customers_affected"] for event in incidents)
    state = "critical" if critical_alerts or affected >= 25 else "degraded" if incidents else "nominal"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission_state": state,
        "summary": {
            "active_incidents": len(incidents),
            "customers_affected": affected,
            "unacknowledged_alerts": len(alert_rows),
            "critical_alerts": critical_alerts,
            "open_tickets": len(ticket_rows),
            "urgent_tickets": urgent_tickets,
            "active_workorders": len(workorder_rows),
            "unassigned_workorders": unassigned_work,
        },
        "incidents": incidents,
        "response_queue": {
            "urgent_tickets": urgent_tickets,
            "unassigned_workorders": unassigned_work,
            "critical_alerts": critical_alerts,
        },
    }


def incident_marker(incident_id: str) -> str:
    normalized = _slug(incident_id)
    return f"[incident:{normalized}]"


def _recommendation(customers_affected: int, devices_offline: int) -> str:
    if customers_affected >= 25:
        return "Open a major-incident bridge and dispatch the nearest available ground crew."
    if devices_offline > 1:
        return "Validate upstream power and backhaul before dispatching individual device work."
    return "Run remote diagnostics, confirm customer impact, then dispatch if recovery fails."


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown-site"
