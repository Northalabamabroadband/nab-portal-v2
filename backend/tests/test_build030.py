from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.router import router
from app.modules.incidents.service import (
    build_incident_command,
    linked_incident_id,
)
from app.modules.platform.router import admin_capabilities


def test_build030_incident_command_exposes_shared_open_queues() -> None:
    now = datetime.now(timezone.utc)
    ticket = SimpleNamespace(
        id="ticket-1",
        client_id="client-7",
        subject="Tower offline",
        description="[incident:launch-site] Investigate customer impact.",
        status="open",
        priority="critical",
        assigned_to=None,
        created_by="noc@example.com",
        created_at=now,
        updated_at=now,
    )
    workorder = SimpleNamespace(
        id="work-1",
        client_id="client-7",
        title="Restore launch site",
        description="[incident:launch-site] Check power and backhaul.",
        status="open",
        priority="high",
        assigned_technician=None,
        service_address="Launch Site",
        scheduled_for=None,
        created_by="noc@example.com",
        created_at=now,
        updated_at=now,
    )
    network = {
        "alarms": [{
            "type": "device_offline",
            "device_id": "router-1",
            "device_name": "Launch Router",
            "site_name": "Launch Site",
            "customers_affected": 27,
        }],
    }

    command = build_incident_command(network, [], [ticket], [workorder])

    assert command["summary"]["active_incidents"] == 1
    assert command["summary"]["open_tickets"] == 1
    assert command["summary"]["active_workorders"] == 1
    assert command["incidents"][0]["response_ready"] is True
    assert command["tickets"][0]["incident_id"] == "launch-site"
    assert command["workorders"][0]["incident_id"] == "launch-site"
    assert command["tickets"][0]["client_id"] == "client-7"
    assert command["workorders"][0]["service_address"] == "Launch Site"


def test_incident_marker_extraction_is_safe() -> None:
    assert linked_incident_id("[incident:rocket-city] Restore service") == (
        "rocket-city"
    )
    assert linked_incident_id("ordinary ticket") is None
    assert linked_incident_id(None) is None


def test_build030_routes_and_capabilities() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/platform/incidents/command" in paths
    assert "/api/v2/platform/incidents/{incident_id}/dispatch" in paths

    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build032"
    assert capabilities["features"]["incident_command_workspace"] == (
        "outages-tickets-and-workorders"
    )
    assert capabilities["features"]["incident_command_management"] == (
        "permission-gated-shared-records"
    )
    assert capabilities["features"]["network_telemetry_navigation"] is False
