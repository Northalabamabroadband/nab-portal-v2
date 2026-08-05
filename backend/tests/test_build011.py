from app.modules.auth.service import DEFAULT_ROLES
from app.modules.platform.router import admin_capabilities


def test_super_admin_default_policy_retains_admin_management() -> None:
    assert "admin.manage" in DEFAULT_ROLES["super_admin"]


def test_access_control_center_is_reported_as_guarded() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["access_control_center"] == "guarded"
