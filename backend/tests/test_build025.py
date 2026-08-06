from app.api.router import router
from app.modules.mikrotik.client import (
    memory_utilization,
    merge_network_neighbors,
    normalize_routeros_base_url,
)
from app.modules.platform.router import admin_capabilities


def test_routeros_url_defaults_to_https_and_appends_rest() -> None:
    assert normalize_routeros_base_url("10.20.30.1") == "https://10.20.30.1/rest"
    assert (
        normalize_routeros_base_url("https://router.nab.local/")
        == "https://router.nab.local/rest"
    )
    assert (
        normalize_routeros_base_url("https://router.nab.local/rest/")
        == "https://router.nab.local/rest"
    )


def test_routeros_memory_utilization_uses_string_values() -> None:
    assert memory_utilization({
        "total-memory": "1000",
        "free-memory": "250",
    }) == 75.0
    assert memory_utilization({"total-memory": "0", "free-memory": "0"}) is None


def test_dhcp_and_arp_neighbors_are_merged_by_normalized_mac() -> None:
    rows = merge_network_neighbors(
        [{
            "mac-address": "00:11:22:33:44:55",
            "address": "10.0.0.25",
            "host-name": "launchpad-tablet",
            "server": "lan-dhcp",
            "status": "bound",
        }],
        [{
            "mac-address": "001122334455",
            "address": "10.0.0.25",
            "interface": "bridge-lan",
            "complete": "true",
        }],
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "dhcp+arp"
    assert rows[0]["active"] is True
    assert rows[0]["hostname"] == "launchpad-tablet"


def test_arp_only_network_neighbor_is_preserved() -> None:
    rows = merge_network_neighbors([], [{
        "mac-address": "AA:BB:CC:DD:EE:FF",
        "address": "10.0.0.30",
        "interface": "bridge-lan",
        "complete": "true",
    }])
    assert len(rows) == 1
    assert rows[0]["source"] == "arp"
    assert rows[0]["ip_address"] == "10.0.0.30"


def test_build025_registers_routeros_routes_and_capabilities() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/mikrotik/status" in paths
    assert "/api/v2/mikrotik/snapshot" in paths
    mikrotik_paths = {path for path in paths if "/mikrotik/" in path}
    assert mikrotik_paths
    assert all("/customers/" not in path for path in mikrotik_paths)
    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build032"
    assert (
        capabilities["features"]["mikrotik_routeros"]
        == "read-only-inventory-and-clients"
    )
    assert (
        capabilities["features"]["mikrotik_tls"]
        == "verified-by-default-with-private-ca-support"
    )
