import pytest
from fastapi import HTTPException

from app.models.desktop import DesktopOutage
from app.modules.desktop.router import (
    DesktopWorkOrderCreate,
    _datetime_from_epoch,
    require_desktop_api_key,
    router,
)


def test_desktop_routes_are_registered_under_isolated_contract() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/desktop/v1/health" in paths
    assert "/api/desktop/v1/snapshot" in paths
    assert "/api/desktop/v1/work-orders" in paths
    assert "/api/desktop/v1/outages" in paths


def test_desktop_api_fails_closed_without_key(monkeypatch) -> None:
    monkeypatch.delenv("NAB_DESKTOP_API_KEY", raising=False)
    with pytest.raises(HTTPException) as caught:
        require_desktop_api_key(None)
    assert caught.value.status_code == 503


def test_desktop_api_rejects_wrong_key(monkeypatch) -> None:
    monkeypatch.setenv("NAB_DESKTOP_API_KEY", "expected-value")
    with pytest.raises(HTTPException) as caught:
        require_desktop_api_key("wrong-value")
    assert caught.value.status_code == 401


def test_desktop_api_accepts_key_without_returning_secret(monkeypatch) -> None:
    monkeypatch.setenv("NAB_DESKTOP_API_KEY", "expected-value")
    fingerprint = require_desktop_api_key("expected-value")
    assert fingerprint != "expected-value"
    assert len(fingerprint) == 64


def test_desktop_work_order_number_matches_database_capacity() -> None:
    payload = DesktopWorkOrderCreate(
        work_order_number="WO-123",
        title="Tower inspection",
    )
    assert payload.work_order_number == "WO-123"
    with pytest.raises(ValueError):
        DesktopWorkOrderCreate(
            work_order_number="X" * 37,
            title="Too long",
        )


def test_desktop_outages_are_postgresql_backed() -> None:
    assert DesktopOutage.__tablename__ == "desktop_outages_v2"
    assert _datetime_from_epoch(1_700_000_000) is not None
