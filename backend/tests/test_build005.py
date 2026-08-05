from app.modules.auth.service import DEFAULT_PERMISSIONS, DEFAULT_ROLES
from app.modules.platform.router import _average
from app.modules.tauc.client import TAUCClient, TAUCError


def test_build005_permissions_are_seeded() -> None:
    assert {"field.read", "field.write", "reports.read", "portal.manage"} <= set(DEFAULT_PERMISSIONS)
    assert "field.read" in DEFAULT_ROLES["field_technician"]


def test_average_ignores_missing_metrics() -> None:
    assert _average([None, 10, 20]) == 15.0
    assert _average([None]) is None


def test_tauc_controls_fail_closed_without_verified_path() -> None:
    client = TAUCClient()
    try:
        client._control_path("", "device-1")
    except TAUCError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("TAUC control path must fail closed")


def test_tauc_control_path_supports_template() -> None:
    client = TAUCClient()
    assert client._control_path("/devices/{device_id}/reboot", "abc") == "/devices/abc/reboot"
