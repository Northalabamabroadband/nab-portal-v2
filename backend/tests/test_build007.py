from types import SimpleNamespace

from app.modules.incidents.service import build_incident_command, build_outage_events


def test_outage_events_group_devices_by_site() -> None:
    events = build_outage_events([
        {"type": "device_offline", "site_name": "Saturn Campus", "device_id": "a", "device_name": "A", "customers_affected": 12},
        {"type": "device_offline", "site_name": "Saturn Campus", "device_id": "b", "device_name": "B", "customers_affected": 8},
        {"type": "latency", "site_name": "Saturn Campus", "device_id": "c", "device_name": "C", "customers_affected": 50},
    ])

    assert len(events) == 1
    assert events[0]["id"] == "saturn-campus"
    assert len(events[0]["devices"]) == 2
    assert events[0]["customers_affected"] == 20


def test_incident_command_reuses_operational_queues() -> None:
    network = {
        "alarms": [
            {"type": "device_offline", "site_name": "Apollo", "device_id": "dev-1", "device_name": "Tower", "customers_affected": 30},
        ]
    }
    alerts = [SimpleNamespace(resource_id="dev-1", severity="critical")]
    tickets = [SimpleNamespace(priority="urgent", status="open")]
    workorders = [SimpleNamespace(assigned_technician=None, status="open")]

    snapshot = build_incident_command(network, alerts, tickets, workorders)

    assert snapshot["mission_state"] == "critical"
    assert snapshot["summary"]["active_incidents"] == 1
    assert snapshot["summary"]["urgent_tickets"] == 1
    assert snapshot["summary"]["unassigned_workorders"] == 1
    assert snapshot["incidents"][0]["alert_count"] == 1
