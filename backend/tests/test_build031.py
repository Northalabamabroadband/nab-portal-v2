import asyncio
import time

from app.api.router import router
from app.modules.networkcenter import service as network_service
from app.modules.platform.router import (
    admin_capabilities,
    incident_command_state,
)
from app.modules.tauc.router import (
    _TAUC_SNAPSHOT_CACHE,
    cached_snapshot_polling_status,
)
from app.modules.tickets.schemas import TicketUpdate
from app.modules.workorders.schemas import WorkOrderUpdate


def reset_network_cache() -> None:
    network_service._DEVICE_CACHE = []
    network_service._DEVICE_CACHE_LOADED_AT = 0.0
    network_service._DEVICE_CACHE_LOADED_AT_ISO = None
    network_service._DEVICE_CACHE_LAST_ERROR = None


def test_build031_registers_coordinated_polling() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/network-center/polling" in paths

    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build033"
    assert capabilities["features"]["network_uisp_poll_coalescing"] is True
    assert capabilities["features"]["network_tauc_polling"] == (
        "rate-limit-safe-no-additional-cloud-requests"
    )


def test_uisp_device_reads_share_one_cache_even_when_inventory_is_empty(
    monkeypatch,
) -> None:
    calls = 0

    async def fake_devices(_client, _limit):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(
        network_service.UISPClient,
        "nms_devices",
        fake_devices,
    )
    reset_network_cache()

    async def read_twice() -> None:
        assert await network_service.load_devices(100) == []
        assert await network_service.load_devices(100) == []

    asyncio.run(read_twice())
    assert calls == 1
    reset_network_cache()


def test_concurrent_force_refreshes_are_coalesced(monkeypatch) -> None:
    calls = 0

    async def fake_devices(_client, _limit):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return [{"id": "device-1", "name": "Rocket City AP"}]

    monkeypatch.setattr(
        network_service.UISPClient,
        "nms_devices",
        fake_devices,
    )
    reset_network_cache()

    async def refresh_together() -> None:
        first, second = await asyncio.gather(
            network_service.load_devices(100, force=True),
            network_service.load_devices(100, force=True),
        )
        assert first == second

    asyncio.run(refresh_together())
    assert calls == 1
    reset_network_cache()


def test_tauc_network_polling_reads_only_fresh_redacted_snapshot_summaries() -> None:
    _TAUC_SNAPSHOT_CACHE.clear()
    _TAUC_SNAPSHOT_CACHE["gateway-1|network"] = (
        time.monotonic() + 10,
        {
            "status": "ready",
            "network_id": "network-1",
            "network_name": "Rocket Wi-Fi",
            "connected_devices": [{"name": "Laptop"}],
            "wifi_networks": [{"ssid": "Rocket City"}],
            "warnings": [],
            "secret_key": "must-not-leak",
        },
    )

    statuses = asyncio.run(cached_snapshot_polling_status())

    assert statuses["gateway-1"]["connected_devices"] == 1
    assert statuses["gateway-1"]["wifi_networks"] == 1
    assert statuses["gateway-1"]["generated_at"]
    assert "secret_key" not in statuses["gateway-1"]
    _TAUC_SNAPSHOT_CACHE.clear()


def test_incident_command_accepts_urgent_records_and_degrades_on_nms_error() -> None:
    assert TicketUpdate(priority="urgent").priority == "urgent"
    assert WorkOrderUpdate(priority="urgent").priority == "urgent"
    assert incident_command_state("nominal", "UISP unavailable") == "degraded"
    assert incident_command_state("critical", "UISP unavailable") == "critical"
