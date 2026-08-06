from __future__ import annotations

from typing import Any, Literal

import httpx

from app.core.settings import get_settings

settings = get_settings()


class UISPError(RuntimeError):
    pass


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in (
        "items",
        "data",
        "results",
        "records",
        "devices",
        "clients",
        "payments",
        "invoices",
        "sites",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = extract_records(value)
            if nested:
                return nested
    result = payload.get("result")
    if isinstance(result, list):
        return [x for x in result if isinstance(x, dict)]
    if isinstance(result, dict):
        nested = extract_records(result)
        return nested or [result]
    return []


class UISPClient:
    def __init__(self, service: Literal["crm", "nms"] = "crm") -> None:
        self.service = service
        if service == "nms":
            self.base_url = (
                settings.uisp_nms_base_url or settings.uisp_base_url
            ).rstrip("/")
            self.token = settings.uisp_nms_api_token or settings.uisp_api_token
        else:
            self.base_url = (
                settings.uisp_crm_base_url or settings.uisp_base_url
            ).rstrip("/")
            self.token = settings.uisp_crm_api_token or settings.uisp_api_token
        self.verify_tls = settings.uisp_verify_tls
        self.timeout = settings.uisp_timeout_seconds
        service_auth_mode = (
            settings.uisp_nms_auth_mode
            if service == "nms"
            else settings.uisp_crm_auth_mode
        )
        self.auth_mode = (
            service_auth_mode or settings.uisp_auth_mode
        ).strip().lower() or "app-key"

    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if not self.token:
            return headers
        if self.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.auth_mode == "x-auth-token":
            headers["x-auth-token"] = self.token
        elif self.auth_mode == "both":
            headers["X-Auth-App-Key"] = self.token
            headers["x-auth-token"] = self.token
        else:
            headers["X-Auth-App-Key"] = self.token
        return headers

    async def get(
        self,
        path: str,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured():
            raise UISPError(f"UISP {self.service.upper()} is not configured")
        path = path if path.startswith("/") else f"/{path}"
        async with httpx.AsyncClient(
            verify=self.verify_tls,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=self.headers(),
                    params=parameters,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:300].replace("\n", " ")
                raise UISPError(
                    f"UISP {self.service.upper()} HTTP "
                    f"{exc.response.status_code} for {path}: {detail}"
                ) from exc
            except httpx.HTTPError as exc:
                raise UISPError(
                    f"Unable to reach UISP {self.service.upper()}: {exc}"
                ) from exc
            except ValueError as exc:
                raise UISPError(
                    f"UISP {self.service.upper()} returned invalid JSON"
                ) from exc

    async def connection_status(self) -> dict[str, Any]:
        path = (
            settings.uisp_nms_devices_path
            if self.service == "nms"
            else settings.uisp_crm_clients_path
        )
        if not self.configured():
            return {
                "service": self.service,
                "configured": False,
                "connected": False,
            }
        try:
            parameters = None if self.service == "nms" else {"limit": 1}
            payload = await self.get(path, parameters)
            return {
                "service": self.service,
                "configured": True,
                "connected": True,
                "base_url": self.base_url,
                "auth_mode": self.auth_mode,
                "path": path,
                "record_count": len(extract_records(payload)),
            }
        except UISPError as exc:
            return {
                "service": self.service,
                "configured": True,
                "connected": False,
                "base_url": self.base_url,
                "auth_mode": self.auth_mode,
                "path": path,
                "detail": str(exc),
            }

    async def nms_devices(
        self,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        payload = await self.get(settings.uisp_nms_devices_path)
        records = extract_records(payload)
        return records[:min(max(limit, 1), 2000)]

    async def nms_sites(
        self,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        payload = await self.get(settings.uisp_nms_sites_path)
        records = extract_records(payload)
        return records[:min(max(limit, 1), 2000)]

    async def clients(
        self,
        limit: int = 250,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        page_size = min(max(limit, 1), 250)
        payload = await self.get(
            settings.uisp_crm_clients_path,
            {"limit": page_size, "offset": max(offset, 0)},
        )
        return extract_records(payload)[:page_size]

    async def search_clients(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = extract_records(
            await self.get(
                settings.uisp_crm_clients_path,
                {
                    "search": query,
                    "limit": min(max(limit, 1), 250),
                },
            )
        )
        needle = query.strip().lower()
        if not needle:
            return rows[:limit]
        return [
            row
            for row in rows
            if needle
            in " ".join(
                str(row.get(key) or "")
                for key in (
                    "id",
                    "firstName",
                    "lastName",
                    "companyName",
                    "username",
                    "email",
                    "phone",
                    "phone1",
                    "mobile",
                )
            ).lower()
        ][:limit]

    async def client(self, client_id: str) -> dict[str, Any]:
        payload = await self.get(
            f"{settings.uisp_crm_clients_path.rstrip('/')}/{client_id}"
        )
        if not isinstance(payload, dict):
            raise UISPError("Invalid UISP CRM client response")
        return payload

    async def client_invoices(
        self,
        client_id: str,
    ) -> list[dict[str, Any]]:
        rows = extract_records(
            await self.get(
                settings.uisp_crm_invoices_path,
                {"clientId": client_id, "limit": 250},
            )
        )
        return [
            row for row in rows
            if str(row.get("clientId")) == str(client_id)
        ]

    async def client_payments(
        self,
        client_id: str,
    ) -> list[dict[str, Any]]:
        rows = extract_records(
            await self.get(
                settings.uisp_crm_payments_path,
                {"clientId": client_id, "limit": 250},
            )
        )
        rows = [
            row for row in rows
            if str(row.get("clientId")) == str(client_id)
        ]
        rows.sort(
            key=lambda row: str(
                row.get("createdDate")
                or row.get("createdAt")
                or row.get("date")
                or ""
            ),
            reverse=True,
        )
        return rows

    async def client_services(
        self,
        client_id: str,
    ) -> list[dict[str, Any]]:
        attempts = (
            (
                "/crm/api/v1.0/clients/services",
                {"clientId": client_id},
            ),
            (
                "/crm/api/v1.0/clients/services",
                {"client": client_id},
            ),
            (
                f"/crm/api/v1.0/clients/{client_id}/services",
                None,
            ),
        )
        for path, parameters in attempts:
            try:
                rows = extract_records(await self.get(path, parameters))
                if rows:
                    return [
                        row for row in rows
                        if str(row.get("clientId") or client_id)
                        == str(client_id)
                    ]
            except UISPError:
                pass
        return []
