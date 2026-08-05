from types import SimpleNamespace

from app.modules.incidents.service import (
    build_incident_command,
    dispatch_resource_id,
    incident_marker,
)


def test_incident_marker_is_normalized() -> None:
    assert incident_marker("Saturn Campus") == "[incident:saturn-campus]"


def test_dispatch_resource_ids_are_stable_and_distinct() -> None:
    first_ticket = dispatch_resource_id("saturn-campus", "ticket")
    retry_ticket = dispatch_resource_id("saturn-campus", "ticket")
    workorder = dispatch_resource_id("saturn-campus", "workorder")

    assert first_ticket == retry_ticket
    assert first_ticket != workorder


def test_existing_response_package_is_detected() -> None:
    marker = incident_marker("saturn-campus")
    network = {
        "alarms": [
            {
                "type": "device_offline",
                "site_name": "Saturn Campus",
                "device_id": "device-1",
                "device_name": "Rocket Link",
                "customers_affected": 10,
            }
        ]
    }
    tickets = [SimpleNamespace(id="ticket-1", description=f"{marker} response")]
    workorders = [SimpleNamespace(
        id="work-1",
        description=f"{marker} dispatch",
        assigned_technician="tech@example.com",
    )]

    snapshot = build_incident_command(network, [], tickets, workorders)

    assert snapshot["incidents"][0]["response_ready"] is True
    assert snapshot["incidents"][0]["ticket_id"] == "ticket-1"
    assert snapshot["incidents"][0]["workorder_id"] == "work-1"
