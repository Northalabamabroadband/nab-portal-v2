from app.models.operations import CustomerTaucAssignment
from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import compact_mac
from app.modules.tauc.schemas import GatewayMappingRequest


def test_tauc_customer_assignment_enforces_unique_device_identity() -> None:
    table = CustomerTaucAssignment.__table__
    assert CustomerTaucAssignment.__tablename__ == "customer_tauc_assignments_v2"
    assert table.c.client_id.index is True
    assert table.c.tauc_device_id.unique is True
    assert table.c.serial_number.unique is True
    assert table.c.mac_address.unique is True


def test_gateway_mapping_payload_is_bounded_and_mac_is_normalized() -> None:
    payload = GatewayMappingRequest(
        client_id="uisp-123",
        serial_number="TAUC-SN-001",
        mac_address="aa:bb:cc:dd:ee:ff",
    )
    assert payload.client_id == "uisp-123"
    assert compact_mac(payload.mac_address or "") == "AABBCCDDEEFF"


def test_tauc_customer_assignments_are_reported() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_customer_assignments"] == "durable-and-unique"
