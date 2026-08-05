from app.models.operations import InventoryItem, SupportTicket, WorkOrder


def test_ticket_defaults() -> None:
    ticket = SupportTicket(subject="Test", created_by="admin@example.com")
    assert ticket.status is None or ticket.status == "open"


def test_workorder_model() -> None:
    order = WorkOrder(title="Install", created_by="admin@example.com")
    assert order.title == "Install"


def test_inventory_model() -> None:
    item = InventoryItem(sku="TEST-1", name="Test Item")
    assert item.sku == "TEST-1"
