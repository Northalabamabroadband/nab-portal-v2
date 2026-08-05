from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.uisp.client import UISPClient, extract_records


def as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


async def billing_summary(limit: int = 250) -> dict[str, Any]:
    uisp = UISPClient()

    clients_payload = await uisp.get(
        "/crm/api/v1.0/clients",
        {"limit": min(max(limit, 1), 250)},
    )
    invoices_payload = await uisp.get(
        "/crm/api/v1.0/invoices",
        {"limit": 1000},
    )
    payments_payload = await uisp.get(
        "/crm/api/v1.0/payments",
        {"limit": 1000},
    )

    clients = extract_records(clients_payload)
    invoices = extract_records(invoices_payload)
    payments = extract_records(payments_payload)

    client_map = {
        str(client.get("id")): client
        for client in clients
        if client.get("id") is not None
    }

    outstanding = Decimal("0")
    overdue = Decimal("0")
    open_invoices = 0
    overdue_invoices = 0

    normalized_invoices: list[dict[str, Any]] = []

    for invoice in invoices:
        client_id = str(invoice.get("clientId") or "")
        client = client_map.get(client_id, {})
        amount_due = as_decimal(
            invoice.get("amountToPay")
            or invoice.get("amountDue")
            or invoice.get("balance")
            or 0
        )

        status = str(
            invoice.get("status")
            or invoice.get("state")
            or ""
        ).lower()

        is_overdue = bool(
            invoice.get("isOverdue")
            or "overdue" in status
        )
        is_open = amount_due > 0 and status not in {"paid", "void", "cancelled"}

        if is_open:
            open_invoices += 1
            outstanding += amount_due

        if is_overdue and amount_due > 0:
            overdue_invoices += 1
            overdue += amount_due

        normalized_invoices.append({
            "id": str(invoice.get("id") or ""),
            "number": invoice.get("number") or invoice.get("invoiceNumber") or invoice.get("id"),
            "client_id": client_id,
            "client_name": (
                client.get("companyName")
                or " ".join(
                    part for part in [
                        str(client.get("firstName") or "").strip(),
                        str(client.get("lastName") or "").strip(),
                    ] if part
                )
                or client.get("username")
                or f"Client {client_id}"
            ),
            "due_date": invoice.get("dueDate") or invoice.get("createdDate"),
            "status": status or "unknown",
            "amount_due": float(amount_due),
            "overdue": is_overdue,
        })

    normalized_invoices.sort(
        key=lambda row: str(row.get("due_date") or ""),
        reverse=True,
    )

    normalized_payments: list[dict[str, Any]] = []

    for payment in payments:
        client_id = str(payment.get("clientId") or "")
        client = client_map.get(client_id, {})
        amount = as_decimal(
            payment.get("amount")
            or payment.get("amountPaid")
            or payment.get("total")
            or 0
        )

        normalized_payments.append({
            "id": str(payment.get("id") or ""),
            "client_id": client_id,
            "client_name": (
                client.get("companyName")
                or " ".join(
                    part for part in [
                        str(client.get("firstName") or "").strip(),
                        str(client.get("lastName") or "").strip(),
                    ] if part
                )
                or client.get("username")
                or f"Client {client_id}"
            ),
            "amount": float(amount),
            "method": payment.get("method") or payment.get("paymentMethod") or "Payment",
            "created_at": payment.get("createdDate") or payment.get("createdAt"),
        })

    normalized_payments.sort(
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    return {
        "customers": len(clients),
        "open_invoices": open_invoices,
        "overdue_invoices": overdue_invoices,
        "outstanding_total": float(outstanding),
        "overdue_total": float(overdue),
        "invoices": normalized_invoices[:500],
        "payments": normalized_payments[:500],
    }
