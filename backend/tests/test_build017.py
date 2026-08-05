from app.models.operations import CustomerNote
from app.modules.platform.router import CustomerNoteCreate, admin_capabilities


def test_customer_note_uses_dedicated_indexed_table() -> None:
    assert CustomerNote.__tablename__ == "customer_notes_v2"
    assert CustomerNote.__table__.c.client_id.index is True


def test_customer_note_payload_is_bounded() -> None:
    assert CustomerNoteCreate(body="Customer requested an afternoon callback.").body
    assert CustomerNoteCreate.model_fields["body"].metadata


def test_customer_activity_timeline_is_reported() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["release"] == "2.0.0-rc1-build017"
    assert capabilities["features"]["customer_activity_timeline"] is True
