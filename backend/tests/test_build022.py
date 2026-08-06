from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import TAUCClient, extract_records


def test_network_client_endpoint_uses_network_id() -> None:
    client = TAUCClient()
    path = client._resource_path(
        "/v1/openapi/network-data-collection/network-clients/{network_id}",
        endpoint_name="connected-device endpoint",
        device_id="device-123",
        network_id="network-456",
        fallback_identifier="network_id",
    )
    assert path == (
        "/v1/openapi/network-data-collection/network-clients/network-456"
    )


def test_network_client_endpoint_supports_provider_placeholder_casing() -> None:
    client = TAUCClient()
    path = client._resource_path(
        "/v1/openapi/network-data-collection/network-clients/{networkId}",
        endpoint_name="connected-device endpoint",
        network_id="network-456",
        fallback_identifier="network_id",
    )
    assert path.endswith("/network-456")


def test_network_client_endpoint_without_placeholder_appends_network_id() -> None:
    client = TAUCClient()
    path = client._resource_path(
        "/v1/openapi/network-data-collection/network-clients",
        endpoint_name="connected-device endpoint",
        network_id="network-456",
        fallback_identifier="network_id",
    )
    assert path.endswith("/network-456")


def test_tauc_network_client_records_are_normalized() -> None:
    rows = extract_records(
        {
            "result": {
                "networkClients": [
                    {
                        "hostName": "Flight Deck Tablet",
                        "ipAddress": "192.0.2.25",
                        "macAddress": "00:11:22:33:44:55",
                    }
                ]
            }
        },
        {"clients", "networkClients", "connectedDevices"},
    )
    assert rows[0]["hostName"] == "Flight Deck Tablet"


def test_build022_reports_network_scoped_tauc_clients() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_network_clients"] == (
        "network-id-scoped"
    )
