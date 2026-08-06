from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.auth.dependencies import require_permission
from app.modules.customers.schemas import CustomerSummary
from app.modules.uisp.client import UISPClient, UISPError

router = APIRouter(prefix="/customers", tags=["customers"])


def first_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def customer_name(record: dict[str, Any]) -> str:
    company = first_value(record, "companyName", "company", "organizationName")
    if isinstance(company, dict):
        company = first_value(company, "name", "displayName")
    if company:
        return str(company)

    full_name = " ".join(
        str(part).strip()
        for part in (
            first_value(record, "firstName", "first_name"),
            first_value(record, "lastName", "last_name"),
        )
        if part
    ).strip()
    return full_name or str(
        first_value(record, "name", "displayName", "username")
        or f"Customer {first_value(record, 'id', 'clientId') or 'unknown'}"
    )


def numeric_value(record: dict[str, Any], *keys: str) -> float | None:
    value = first_value(record, *keys)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def customer_address(record: dict[str, Any]) -> str:
    address = first_value(
        record,
        "address",
        "serviceAddress",
        "billingAddress",
        "invoiceAddress",
    )
    if isinstance(address, str):
        return address.strip()
    if isinstance(address, dict):
        values = [
            first_value(address, "street1", "street", "address1", "line1"),
            first_value(address, "street2", "address2", "line2"),
            first_value(address, "city"),
            first_value(address, "state", "stateCode"),
            first_value(address, "zipCode", "zip", "postalCode"),
        ]
    else:
        values = [
            first_value(record, "street1", "street", "address1"),
            first_value(record, "city"),
            first_value(record, "state", "stateCode"),
            first_value(record, "zipCode", "zip", "postalCode"),
        ]
    return ", ".join(str(value).strip() for value in values if value)


def normalize_customer_directory_item(record: dict[str, Any]) -> dict[str, Any]:
    client_id = str(first_value(record, "id", "clientId", "_id") or "")
    raw_status = str(
        first_value(record, "status", "accountStatus", "state") or ""
    ).strip().lower()
    inactive_states = {"inactive", "disabled", "terminated", "archived"}
    suspended = bool(record.get("isSuspended")) or raw_status == "suspended"
    active = (
        record.get("isActive") is not False
        and raw_status not in inactive_states
        and not suspended
    )
    past_due = (
        bool(record.get("isPastDue"))
        or bool(record.get("hasOverdueInvoice"))
        or raw_status in {"past_due", "past due", "overdue"}
    )

    email = first_value(record, "email", "primaryEmail", "contactEmail")
    phone = first_value(
        record,
        "phone",
        "phone1",
        "mobile",
        "primaryPhone",
        "contactPhone",
    )
    return {
        "id": client_id,
        "name": customer_name(record),
        "account_number": str(
            first_value(
                record,
                "accountNumber",
                "clientNumber",
                "userIdent",
                "username",
            )
            or client_id
        ),
        "email": str(email).strip() if email else None,
        "phone": str(phone).strip() if phone else None,
        "address": customer_address(record) or None,
        "status": {
            "active": active,
            "suspended": suspended,
            "past_due": past_due,
            "label": "Past due" if past_due else "Suspended" if suspended else "Active" if active else "Inactive",
        },
        "balance": numeric_value(
            record,
            "accountBalance",
            "balance",
            "currentBalance",
        ),
    }


@router.get("/capabilities")
def customer_capabilities() -> dict[str, object]:
    return {
        "customer_360": True,
        "directory": "uisp-crm-authoritative",
        "billing": True,
        "services": True,
        "equipment": True,
        "tickets": True,
        "documents": True,
        "uisp_live_data": True,
        "status": "rc1-build032",
    }


@router.get("/directory")
async def customer_directory(
    claims: Annotated[dict, Depends(require_permission("customers.read"))],
    q: str = Query(default="", max_length=160),
    limit: int = Query(default=250, ge=1, le=250),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, Any]:
    query = q.strip()
    uisp = UISPClient()
    try:
        if query:
            rows = await uisp.search_clients(query, limit)
            has_more = False
        else:
            rows = await uisp.clients(limit=limit, offset=offset)
            has_more = len(rows) == limit
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    items = [
        normalize_customer_directory_item(row)
        for row in rows
        if first_value(row, "id", "clientId", "_id")
    ]
    items.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    return {
        "query": query,
        "offset": 0 if query else offset,
        "limit": limit,
        "count": len(items),
        "has_more": has_more,
        "summary": {
            "visible": len(items),
            "active": sum(item["status"]["active"] for item in items),
            "inactive": sum(not item["status"]["active"] for item in items),
            "past_due": sum(item["status"]["past_due"] for item in items),
        },
        "items": items,
    }


@router.get("/{client_id}", response_model=CustomerSummary)
async def customer_summary(
    client_id: str,
    claims: Annotated[
        dict,
        Depends(require_permission("customers.read")),
    ],
) -> CustomerSummary:
    uisp = UISPClient()

    try:
        client, services, invoices, payments = await asyncio.gather(
            uisp.client(client_id),
            uisp.client_services(client_id),
            uisp.client_invoices(client_id),
            uisp.client_payments(client_id),
        )
    except UISPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CustomerSummary(
        client=client,
        services=services,
        invoices=invoices,
        payments=payments,
        last_payment=payments[0] if payments else None,
    )
