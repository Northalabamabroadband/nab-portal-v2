import asyncio

from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import TAUCClient


def test_tauc_network_id_can_be_resolved_by_network_name() -> None:
    client = TAUCClient()

    async def fake_request(
        method: str,
        path: str,
        *,
        params=None,
        **kwargs,
    ):
        assert method == "GET"
        assert path == "/v1/openapi/network-system-management/id"
        assert params == {"networkName": "Rocket City Home"}
        return {
            "result": [
                {"networkName": "Other Network", "id": 41},
                {"networkName": "Rocket City Home", "id": 73},
            ]
        }

    client.request = fake_request  # type: ignore[method-assign]
    assert asyncio.run(
        client.network_id_by_name("Rocket City Home")
    ) == "73"


def test_tauc_network_id_lookup_is_case_insensitive() -> None:
    client = TAUCClient()

    async def fake_request(*args, **kwargs):
        return {
            "result": [
                {"networkName": "ROCKET CITY HOME", "id": "network-73"}
            ]
        }

    client.request = fake_request  # type: ignore[method-assign]
    assert asyncio.run(
        client.network_id_by_name("rocket city home")
    ) == "network-73"


def test_build023_reports_network_id_recovery() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_network_id_resolution"] == (
        "assignment-or-network-name"
    )
