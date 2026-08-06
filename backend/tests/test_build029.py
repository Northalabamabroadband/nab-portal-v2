from app.api.router import router
from app.modules.customers.router import normalize_customer_directory_item
from app.modules.platform.router import admin_capabilities


def test_build029_registers_distinct_customer_and_mission_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/v2/customers/directory" in paths
    assert "/api/v2/platform/mission-control" in paths


def test_customer_directory_normalization_is_safe_and_predictable() -> None:
    item = normalize_customer_directory_item({
        "id": 42,
        "firstName": "Ada",
        "lastName": "Lovelace",
        "accountNumber": "NAB-0042",
        "email": "ada@example.com",
        "phone1": "256-555-0100",
        "serviceAddress": {
            "street1": "1 Rocket Way",
            "city": "Huntsville",
            "state": "AL",
            "zipCode": "35805",
        },
        "isActive": True,
        "hasOverdueInvoice": True,
        "accountBalance": "89.50",
        "apiToken": "must-not-leak",
    })

    assert item["id"] == "42"
    assert item["name"] == "Ada Lovelace"
    assert item["account_number"] == "NAB-0042"
    assert item["address"] == "1 Rocket Way, Huntsville, AL, 35805"
    assert item["status"] == {
        "active": True,
        "suspended": False,
        "past_due": True,
        "label": "Past due",
    }
    assert item["balance"] == 89.5
    assert "apiToken" not in item


def test_build029_reports_customer_directory_and_mission_control() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build032"
    assert capabilities["features"]["mission_control_overview"] == (
        "consolidated-network-and-operations"
    )
    assert capabilities["features"]["customer_directory"] == (
        "uisp-crm-authoritative"
    )
