import asyncio

from app.modules.networkcenter import router as network_router
from app.modules.platform.router import (
    admin_capabilities,
    network_polling_error,
)


class EmptyScalars:
    def all(self):
        return []


class EmptySession:
    def scalars(self, _statement):
        return EmptyScalars()


def test_stale_uisp_cache_preserves_the_upstream_failure_signal() -> None:
    network = {
        "cache": {
            "fresh": False,
            "last_error": "UISP NMS is unavailable",
        },
    }

    assert network_polling_error(network) == "UISP NMS is unavailable"
    assert network_polling_error({"cache": {"last_error": None}}) is None
    assert network_polling_error({}) is None


def test_disabled_mikrotik_collector_does_not_create_false_outages(
    monkeypatch,
) -> None:
    async def fake_overview(_limit, *, force=False):
        return {
            "summary": {},
            "devices": [],
            "alarms": [],
            "sites": [],
            "cache": {
                "fresh": True,
                "loaded_at": "2026-08-06T00:00:00+00:00",
                "age_seconds": 1,
                "ttl_seconds": 15,
                "last_error": None,
            },
        }

    async def fake_fleet_status():
        return {
            "collector": {
                "enabled": False,
                "detail": "Collector disabled",
            },
            "routers": [{
                "key": "core",
                "name": "Core Router",
                "site": "Rocket City",
                "role": "core",
                "configured": True,
                "enabled": True,
                "connected": False,
                "detail": "Waiting for collector telemetry",
            }],
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

    mikrotik = next(
        source
        for source in result["sources"]
        if source["id"] == "mikrotik"
    )
    router_device = next(
        device
        for device in result["devices"]
        if device["source"] == "mikrotik"
    )
    assert mikrotik["state"] == "unconfigured"
    assert router_device["status"] == "unknown"
    assert not [
        alarm
        for alarm in result["alarms"]
        if alarm["source"] == "mikrotik"
    ]


def test_build032_reports_portal_recovery_capabilities() -> None:
    capabilities = admin_capabilities({})

    assert capabilities["release"] == "2.0.0-rc1-build032"
    assert capabilities["features"]["portal_render_recovery"] is True
    assert capabilities["features"]["portal_saved_session_validation"] is True
    assert (
        capabilities["features"]["network_polling_response_validation"]
        is True
    )
