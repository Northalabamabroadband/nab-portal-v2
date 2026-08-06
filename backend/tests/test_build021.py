from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import extract_records


def test_wifi_records_are_normalized_from_nested_tauc_payload() -> None:
    payload = {
        "result": {
            "wifiSsids": [
                {"ssid": "NAB Home", "band": "5 GHz", "enabled": True},
                {"ssid": "NAB IoT", "band": "2.4 GHz", "enabled": True},
            ]
        }
    }
    rows = extract_records(payload, {"ssids", "wifiSsids", "networks"})
    assert [row["ssid"] for row in rows] == ["NAB Home", "NAB IoT"]


def test_connected_devices_are_normalized_from_device_info() -> None:
    payload = {
        "result": {
            "topology": {
                "connectedDevices": [
                    {"hostName": "Living Room TV", "ipAddress": "192.0.2.20"}
                ]
            }
        }
    }
    rows = extract_records(
        payload,
        {"clients", "clientList", "connectedDevices", "stations"},
    )
    assert rows[0]["hostName"] == "Living Room TV"


def test_live_tauc_gateway_snapshot_is_reported() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_live_gateway_snapshot"] == (
        "wifi-and-connected-devices"
    )
