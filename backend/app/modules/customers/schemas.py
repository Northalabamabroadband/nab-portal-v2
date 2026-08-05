from typing import Any

from pydantic import BaseModel


class CustomerSummary(BaseModel):
    client: dict[str, Any]
    services: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    last_payment: dict[str, Any] | None
