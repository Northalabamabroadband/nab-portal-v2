import json

import pytest

from app.api.router import router
from app.models.mikrotik import MikroTikInterfaceRollup
from app.modules.mikrotik.client import MikroTikError, load_router_profiles
from app.modules.mikrotik.collector import calculate_interface_rates


def test_build027_registers_fleet_and_history_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/mikrotik/fleet" in paths
    assert "/api/v2/mikrotik/routers/{router_key}/snapshot" in paths
    assert "/api/v2/mikrotik/routers/{router_key}/history" in paths
    assert all(
        "/customers/" not in path
        for path in paths
        if "/mikrotik/" in path
    )


def test_router_profiles_load_from_secret_without_exposing_password(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MIKROTIK_TEST_PASSWORD", "private-value")
    source = tmp_path / "routers.json"
    source.write_text(json.dumps({
        "routers": [{
            "key": "core-1",
            "name": "Core 1",
            "site": "Main",
            "role": "core",
            "base_url": "https://router.example.com/rest",
            "username": "portal",
            "password_env": "MIKROTIK_TEST_PASSWORD",
            "poll_interval_seconds": 2,
        }]
    }))

    profiles = load_router_profiles(str(source))

    assert len(profiles) == 1
    assert profiles[0].password == "private-value"
    assert profiles[0].public_dict()["configured"] is True
    assert "password" not in profiles[0].public_dict()


def test_router_profile_keys_must_be_unique(tmp_path) -> None:
    source = tmp_path / "routers.json"
    source.write_text(json.dumps([
        {"key": "duplicate"},
        {"key": "duplicate"},
    ]))

    with pytest.raises(MikroTikError, match="Duplicate"):
        load_router_profiles(str(source))


def test_collector_rate_calculation_handles_counter_reset() -> None:
    rates, counters = calculate_interface_rates(
        [{"name": "sfp1", "rx-byte": "200", "tx-byte": "400"}],
        {"sfp1": (10.0, 100, 200)},
        12.0,
    )
    assert rates["sfp1"]["rx"] == 400.0
    assert rates["sfp1"]["tx"] == 800.0

    reset_rates, _ = calculate_interface_rates(
        [{"name": "sfp1", "rx-byte": "10", "tx-byte": "20"}],
        counters,
        14.0,
    )
    assert reset_rates["sfp1"]["rx"] == 0.0
    assert reset_rates["sfp1"]["tx"] == 0.0


def test_rollup_table_prevents_duplicate_router_interface_buckets() -> None:
    constraints = {
        constraint.name
        for constraint in MikroTikInterfaceRollup.__table__.constraints
    }
    assert "uq_mikrotik_rollup_router_interface_bucket" in constraints
