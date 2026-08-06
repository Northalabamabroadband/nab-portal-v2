import asyncio

from app.modules.networkcenter import router as network_router
from app.modules.networkcenter.service import derive_alarms, normalize_device
from app.modules.platform.router import admin_capabilities


class EmptyScalars:
    def all(self):
        return []


class EmptySession:
    def scalars(self, _statement):
        return EmptyScalars()


def test_nested_uisp_nms_device_telemetry_is_normalized() -> None:
    device = normalize_device({
        "id": "device-1",
        "identification": {
            "name": "Rocket AP",
            "modelName": "Rocket Prism 5AC",
            "role": "access-point",
            "firmwareVersion": "8.7.11",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ipAddress": "100.80.20.10",
            "site": {
                "id": "site-1",
                "name": "Launch Complex",
                "location": {
                    "latitude": 34.7304,
                    "longitude": -86.5861,
                },
            },
        },
        "overview": {
            "status": "active",
            "cpu": {"value": 31},
            "ram": "48%",
            "temperature": {"current": 53.2},
            "signal": "-61 dBm",
            "latency": "12 ms",
            "packetLoss": "0.5%",
            "uptime": 86400,
            "rxRate": 1250000,
            "txRate": 500000,
            "lastSeenAt": "2026-08-05T16:30:00Z",
            "clientCount": 7,
        },
    })

    assert device["id"] == "device-1"
    assert device["name"] == "Rocket AP"
    assert device["model"] == "Rocket Prism 5AC"
    assert device["type"] == "access-point"
    assert device["status"] == "online"
    assert device["site_id"] == "site-1"
    assert device["site_name"] == "Launch Complex"
    assert device["ip"] == "100.80.20.10"
    assert device["mac"] == "AA:BB:CC:DD:EE:FF"
    assert device["firmware"] == "8.7.11"
    assert device["cpu"] == 31
    assert device["memory"] == 48
    assert device["temperature"] == 53.2
    assert device["signal"] == -61
    assert device["latency"] == 12
    assert device["packet_loss"] == 0.5
    assert device["uptime_seconds"] == 86400
    assert device["rx_rate_bps"] == 1250000
    assert device["tx_rate_bps"] == 500000
    assert device["last_seen_at"] == "2026-08-05T16:30:00Z"
    assert device["customer_count"] == 7
    assert device["latitude"] == 34.7304
    assert device["longitude"] == -86.5861
    assert device["telemetry_fields"] == 10


def test_uisp_interface_and_wireless_fallbacks_are_supported() -> None:
    device = normalize_device({
        "deviceId": "device-2",
        "overview": {"connected": True},
        "interfaces": [{
            "name": "eth0",
            "ipAddress": "100.80.20.11",
            "macAddress": "11:22:33:44:55:66",
        }],
        "wireless": [{"rssi": "-76 dBm"}],
    })

    assert device["status"] == "online"
    assert device["ip"] == "100.80.20.11"
    assert device["mac"] == "11:22:33:44:55:66"
    assert device["signal"] == -76
    alarms = derive_alarms([device])
    assert [alarm["type"] for alarm in alarms] == ["weak_signal"]


def test_coordinated_polling_exposes_normalized_uisp_telemetry(
    monkeypatch,
) -> None:
    device = normalize_device({
        "id": "device-3",
        "identification": {"name": "Backhaul"},
        "overview": {
            "status": "active",
            "cpu": 25,
            "rxRate": 8000000,
        },
    })

    async def fake_overview(_limit, *, force=False):
        return {
            "summary": {"customers_affected": 0},
            "devices": [device],
            "alarms": [],
            "sites": [],
            "cache": {
                "fresh": True,
                "loaded_at": "2026-08-05T16:30:00Z",
                "age_seconds": 1,
                "ttl_seconds": 15,
                "last_error": None,
            },
        }

    async def fake_fleet_status():
        return {
            "collector": {"enabled": False},
            "routers": [],
        }

    async def fake_tauc_cache():
        return {}

    monkeypatch.setattr(network_router, "overview", fake_overview)
    monkeypatch.setattr(
        network_router.collector,
        "fleet_status",
        fake_fleet_status,
    )
    monkeypatch.setattr(
        network_router,
        "cached_snapshot_polling_status",
        fake_tauc_cache,
    )

    result = asyncio.run(network_router.coordinated_device_polling(
        claims={},
        session=EmptySession(),
        limit=100,
        force=False,
    ))

    network_device = result["devices"][0]
    uisp_source = next(
        source for source in result["sources"]
        if source["id"] == "uisp"
    )
    assert network_device["cpu"] == 25
    assert network_device["rx_rate_bps"] == 8000000
    assert "raw" not in network_device
    assert result["summary"]["devices_reporting_telemetry"] == 1
    assert uisp_source["telemetry_device_count"] == 1
    assert "1 of 1 devices reporting live" in uisp_source["detail"]


def test_build033_reports_uisp_live_telemetry_capabilities() -> None:
    capabilities = admin_capabilities({})

    assert capabilities["release"] == "2.0.0-rc1-build033"
    assert capabilities["features"]["uisp_nested_telemetry_mapping"] is True
    assert capabilities["features"]["uisp_live_device_metrics"] is True
    assert (
        capabilities["features"]["uisp_telemetry_polling"]
        == "shared-device-list-cache"
    )
