from app.modules.platform.router import capability_parity


def test_capability_parity_covers_core_operations() -> None:
    report = capability_parity({})
    by_domain = {row["domain"]: row for row in report["capabilities"]}

    assert by_domain["Support tickets"]["write"] is True
    assert by_domain["Work orders and dispatch"]["write"] is True
    assert by_domain["Inventory"]["write"] is True
    assert by_domain["Fiber assets and mapping"]["write"] is True
    assert report["total_domains"] == len(report["capabilities"])


def test_external_authoritative_systems_are_not_misreported_as_writable() -> None:
    report = capability_parity({})
    by_domain = {row["domain"]: row for row in report["capabilities"]}

    assert by_domain["Billing and payments"]["write"] is False
    assert by_domain["Network telemetry"]["write"] is False
    assert by_domain["Managed Wi-Fi"]["write"] == "configuration-gated"
