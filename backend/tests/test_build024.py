from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import TAUCClient, tauc_request_delay
from app.modules.tauc.router import cacheable_snapshot, snapshot_cache_key


def test_tauc_request_delay_honors_global_cooldown() -> None:
    assert tauc_request_delay(
        last_started_at=9.0,
        now=10.0,
        minimum_interval=1.35,
        cooldown_until=13.0,
    ) == 3.0


def test_tauc_client_enforces_interval_safety_floor() -> None:
    client = TAUCClient()
    assert client.minimum_request_interval >= 1.35
    assert client.rate_limit_backoff >= 3.0


def test_duplicate_snapshot_keys_normalize_gateway_identity() -> None:
    first = snapshot_cache_key(
        "device-1",
        "",
        "Rocket City Home",
        "EX920V123",
        "00:11:22:33:44:55",
    )
    second = snapshot_cache_key(
        "device-1",
        "",
        "rocket city home",
        "ex920v123",
        "001122334455",
    )
    assert first == second


def test_rate_limited_snapshots_are_not_cached() -> None:
    assert not cacheable_snapshot({
        "network_id": "network-1",
        "warnings": [
            "TAUC error -70307: visit count reached the rate limit"
        ],
    })


def test_resolved_snapshots_are_cacheable() -> None:
    assert cacheable_snapshot({
        "network_id": "network-1",
        "warnings": [],
    })


def test_build024_reports_tauc_request_coordination() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_request_throttle"] == (
        "one-per-second-with-safe-get-retry"
    )
    assert capabilities["features"]["tauc_rate_limit_cooldown"] == (
        "global-three-second-backoff"
    )
    assert capabilities["features"]["tauc_snapshot_coalescing"] == (
        "in-flight-and-short-cache"
    )
