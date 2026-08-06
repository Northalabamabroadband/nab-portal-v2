import asyncio

import pytest
from fastapi import HTTPException

from app.api.router import router
from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import TAUCClient
from app.modules.tauc.router import (
    _TAUC_SNAPSHOT_CACHE,
    invalidate_snapshot_cache,
    validate_ssid,
    validate_wifi_password,
)


def test_build028_registers_managed_wifi_fleet() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/tauc/fleet" in paths
    assert "/api/v2/tauc/devices/{device_id}/snapshot" in paths
    assert "/api/v2/tauc/controls/wifi/ssid" in paths
    assert "/api/v2/tauc/controls/wifi/password" in paths
    assert "/api/v2/tauc/controls/reboot" in paths
    assert "/api/v2/tauc/controls/diagnostics" in paths


def test_managed_wifi_configuration_never_exposes_credentials() -> None:
    public = TAUCClient().configuration_status()
    assert "access_key" not in public
    assert "secret_key" not in public
    assert "client_key" not in public
    assert set(public["controls"]) == {
        "ssid_update",
        "password_update",
        "reboot",
        "provider_diagnostics",
    }


def test_wifi_name_and_password_validation() -> None:
    assert validate_ssid(" Rocket City WiFi ") == "Rocket City WiFi"
    assert validate_wifi_password("mission-control-28") == "mission-control-28"
    assert validate_wifi_password("a" * 64) == "a" * 64

    with pytest.raises(HTTPException, match="32 UTF-8 bytes"):
        validate_ssid("🚀" * 9)
    with pytest.raises(HTTPException, match="8–63"):
        validate_wifi_password("short")
    with pytest.raises(HTTPException, match="8–63"):
        validate_wifi_password("z" * 64)


def test_successful_control_can_invalidate_only_its_gateway_cache() -> None:
    _TAUC_SNAPSHOT_CACHE.clear()
    _TAUC_SNAPSHOT_CACHE["gateway-1|network"] = (100.0, {"status": "ready"})
    _TAUC_SNAPSHOT_CACHE["gateway-2|network"] = (100.0, {"status": "ready"})

    asyncio.run(invalidate_snapshot_cache("gateway-1"))

    assert "gateway-1|network" not in _TAUC_SNAPSHOT_CACHE
    assert "gateway-2|network" in _TAUC_SNAPSHOT_CACHE
    _TAUC_SNAPSHOT_CACHE.clear()


def test_build028_reports_managed_wifi_operations() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build032"
    assert capabilities["features"]["managed_wifi_operations"] == (
        "fleet-clients-controls-and-diagnostics"
    )
    assert capabilities["features"]["managed_wifi_control_responses"] == (
        "secret-redacted"
    )
