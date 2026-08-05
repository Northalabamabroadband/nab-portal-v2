from app.modules.auth.service import DEFAULT_PERMISSIONS
from app.modules.platform.router import admin_capabilities, capability_parity


def test_customer_action_center_uses_existing_permissions() -> None:
    assert {"customers.write", "network.write", "wifi.read", "wifi.write"} <= set(DEFAULT_PERMISSIONS)


def test_customer_action_center_is_reported_as_gated() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["release"].startswith("2.0.0-rc1-build")
    assert capabilities["features"]["customer_action_center"] == "permission-and-configuration-gated"


def test_customer_360_remains_shared_capability_source() -> None:
    report = capability_parity({})
    customer = next(row for row in report["capabilities"] if row["domain"] == "Customer 360")
    assert customer["read"] is True
    assert customer["write"] is True
