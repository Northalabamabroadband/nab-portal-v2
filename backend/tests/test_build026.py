from app.api.router import router
from app.modules.mikrotik.router import (
    MAX_THROUGHPUT_INTERFACES,
    interface_throughput_sample,
)


def test_build026_registers_read_only_throughput_route() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/mikrotik/throughput" in paths
    assert all(
        "/customers/" not in path
        for path in paths
        if "/mikrotik/" in path
    )


def test_throughput_sample_filters_and_orders_selected_interfaces() -> None:
    sample = interface_throughput_sample(
        [
            {
                ".id": "*1",
                "name": "ether1",
                "running": "true",
                "disabled": "false",
                "rx-byte": "1000",
                "tx-byte": "2000",
            },
            {
                ".id": "*2",
                "name": "sfp-sfpplus1",
                "running": "false",
                "disabled": "false",
                "rx-byte": "3000",
                "tx-byte": "4000",
            },
        ],
        ["sfp-sfpplus1", "missing", "ether1"],
    )
    assert [row["name"] for row in sample["interfaces"]] == [
        "sfp-sfpplus1",
        "ether1",
    ]
    assert sample["interfaces"][0]["rx_bytes"] == 3000
    assert sample["interfaces"][1]["tx_bytes"] == 2000
    assert sample["missing"] == ["missing"]


def test_throughput_sample_handles_routeros_counter_resets_safely() -> None:
    sample = interface_throughput_sample(
        [{
            "name": "ether1",
            "rx-byte": "-1",
            "tx-byte": "not-a-number",
        }],
        ["ether1"],
    )
    assert sample["interfaces"][0]["rx_bytes"] == 0
    assert sample["interfaces"][0]["tx_bytes"] == 0
    assert MAX_THROUGHPUT_INTERFACES == 6
