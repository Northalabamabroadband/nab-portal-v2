from __future__ import annotations

import asyncio
from typing import Any

from app.modules.tauc.client import TAUCClient, TAUCError
from app.modules.uisp.client import UISPClient, UISPError


def customer_name(client: dict[str, Any]) -> str:
    company = str(client.get("companyName") or "").strip()
    if company:
        return company

    full = " ".join(
        part
        for part in [
            str(client.get("firstName") or "").strip(),
            str(client.get("lastName") or "").strip(),
        ]
        if part
    )
    return full or str(client.get("username") or "Customer")


def customer_address(client: dict[str, Any]) -> str:
    address = client.get("address")

    if isinstance(address, dict):
        parts = [
            address.get("address1"),
            address.get("address2"),
            address.get("city"),
            address.get("state"),
            address.get("zipCode"),
        ]
        return ", ".join(str(part) for part in parts if part)

    if isinstance(address, str):
        return address

    parts = [
        client.get("street1"),
        client.get("street2"),
        client.get("city"),
        client.get("state"),
        client.get("zipCode"),
    ]
    return ", ".join(str(part) for part in parts if part)


async def customer_360(client_id: str) -> dict[str, Any]:
    uisp = UISPClient()

    client, services, invoices, payments = await asyncio.gather(
        uisp.client(client_id),
        uisp.client_services(client_id),
        uisp.client_invoices(client_id),
        uisp.client_payments(client_id),
    )

    result: dict[str, Any] = {
        "client_id": client_id,
        "name": customer_name(client),
        "email": client.get("email") or client.get("username"),
        "phone": client.get("phone") or client.get("phone1") or client.get("mobile"),
        "address": customer_address(client),
        "status": {
            "active": bool(client.get("isActive", True)),
            "suspended": bool(
                client.get("isSuspended")
                or client.get("hasSuspendedService")
            ),
            "past_due": bool(client.get("hasOverdueInvoice")),
        },
        "billing": {
            "balance": client.get("accountBalance"),
            "outstanding": client.get("accountOutstanding"),
            "last_payment": payments[0] if payments else None,
            "payments": payments,
            "invoices": invoices,
        },
        "services": services,
        "gateway": None,
        "raw_client": client,
    }

    serial_number = (
        client.get("gatewaySerialNumber")
        or client.get("deviceSerialNumber")
        or client.get("serialNumber")
    )
    mac_address = (
        client.get("gatewayMac")
        or client.get("deviceMac")
        or client.get("macAddress")
    )

    if serial_number:
        tauc = TAUCClient()

        try:
            device, network = await asyncio.gather(
                tauc.device_lookup(
                    serial_number=str(serial_number),
                    mac_address=str(mac_address) if mac_address else None,
                ),
                tauc.network_lookup(
                    serial_number=str(serial_number),
                    mac_address=str(mac_address) if mac_address else None,
                ),
            )
            result["gateway"] = {
                "device": device,
                "network": network,
            }
        except TAUCError as exc:
            result["gateway_error"] = str(exc)

    return result
