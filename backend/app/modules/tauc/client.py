from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

import httpx

from app.core.settings import get_settings

settings = get_settings()
_TAUC_REQUEST_LOCK = asyncio.Lock()
_last_tauc_request_started_at = 0.0
_tauc_cooldown_until = 0.0


class TAUCError(RuntimeError):
    pass


def compact_mac(value: str) -> str:
    return "".join(character for character in value if character.isalnum()).upper()


def result_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def normalized_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def extract_records(payload: Any, candidate_keys: set[str]) -> list[dict[str, Any]]:
    targets = {normalized_key(key) for key in candidate_keys}

    def visit(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            for key, nested in value.items():
                if (
                    normalized_key(str(key)) in targets
                    and isinstance(nested, list)
                ):
                    rows = [item for item in nested if isinstance(item, dict)]
                    if rows:
                        return rows
            for nested in value.values():
                rows = visit(nested)
                if rows:
                    return rows
        elif isinstance(value, list):
            for nested in value:
                rows = visit(nested)
                if rows:
                    return rows
        return []

    return visit(payload)


def is_tauc_rate_limited(status_code: int, payload: Any) -> bool:
    return status_code == 429 or (
        isinstance(payload, dict)
        and str(payload.get("errorCode") or "") == "-70307"
    )


def should_retry_tauc_request(
    method: str,
    status_code: int,
    payload: Any,
    attempt: int,
) -> bool:
    return (
        method.upper() == "GET"
        and attempt == 0
        and is_tauc_rate_limited(status_code, payload)
    )


def tauc_request_delay(
    last_started_at: float,
    now: float,
    minimum_interval: float,
    cooldown_until: float = 0.0,
) -> float:
    return max(
        0.0,
        minimum_interval - (now - last_started_at),
        cooldown_until - now,
    )


def tauc_error_message(
    status_code: int,
    method: str,
    base_url: str,
    path: str,
    payload: Any,
    reason: str,
) -> str:
    code = (
        payload.get("errorCode", status_code)
        if isinstance(payload, dict)
        else status_code
    )
    message = payload.get("msg", reason) if isinstance(payload, dict) else reason
    if status_code == 404:
        return (
            f"TAUC endpoint not found: {method.upper()} {base_url}{path}. "
            "Check TAUC_BASE_URL and the configured TAUC lookup path for this "
            "tenant region."
        )
    return f"TAUC error {code}: {message}"


class TAUCClient:
    def __init__(self) -> None:
        self.base_url = settings.tauc_base_url.rstrip("/")
        self.access_key = settings.tauc_access_key.strip()
        self.secret_key = settings.tauc_secret_key.strip()
        self.client_cert = Path(settings.tauc_client_cert)
        self.client_key = Path(settings.tauc_client_key)
        self.verify_tls = settings.tauc_verify_tls
        self.timeout = settings.tauc_timeout_seconds
        self.minimum_request_interval = max(
            1.35,
            settings.tauc_min_request_interval_seconds,
        )
        self.rate_limit_backoff = max(
            self.minimum_request_interval,
            settings.tauc_rate_limit_backoff_seconds,
        )

    def configured(self) -> bool:
        return bool(
            self.base_url
            and self.access_key
            and self.secret_key
            and self.client_cert.is_file()
            and self.client_key.is_file()
        )

    def _body(self, payload: Any) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()

    def _authorization(
        self,
        path: str,
        body: bytes | None,
    ) -> tuple[str, str | None]:
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        parts: list[str] = []
        content_md5 = None
        if body:
            content_md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
            parts.append(content_md5)
        parts.extend((timestamp, nonce, path))
        signature = hmac.new(
            self.secret_key.encode(),
            "\n".join(parts).encode(),
            hashlib.sha256,
        ).hexdigest()
        return (
            f"Nonce={nonce},AccessKey={self.access_key},"
            f"Signature={signature},Timestamp={timestamp}",
            content_md5,
        )

    def signing_headers(
        self,
        *,
        method: str,
        path: str,
        body: Any = None,
    ) -> dict[str, str]:
        del method  # TAUC signs content metadata and the request path.
        path = path if path.startswith("/") else f"/{path}"
        encoded = self._body(body) if body is not None else None
        authorization, content_md5 = self._authorization(path, encoded)
        fields = dict(
            item.split("=", 1)
            for item in authorization.split(",")
            if "=" in item
        )
        headers = {
            "Accept": "application/json",
            "X-Authorization": authorization,
            "X-Timestamp": fields.get("Timestamp", ""),
            "X-Nonce": fields.get("Nonce", ""),
        }
        if encoded is not None:
            headers.update({
                "Content-Type": "application/json",
                "Content-MD5": content_md5 or "",
            })
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_data: Any = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        global _last_tauc_request_started_at, _tauc_cooldown_until

        if not self.configured():
            raise TAUCError(
                "TAUC access key, secret key, and mTLS certificate/key are required"
            )

        method = method.upper()
        path = path if path.startswith("/") else f"/{path}"
        body = self._body(json_data) if json_data is not None else None

        async with httpx.AsyncClient(
            cert=(str(self.client_cert), str(self.client_key)),
            verify=self.verify_tls,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            for attempt in range(2 if method == "GET" else 1):
                async with _TAUC_REQUEST_LOCK:
                    now = time.monotonic()
                    delay = tauc_request_delay(
                        _last_tauc_request_started_at,
                        now,
                        self.minimum_request_interval,
                        _tauc_cooldown_until,
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                    _last_tauc_request_started_at = time.monotonic()
                    authorization, content_md5 = self._authorization(path, body)
                    headers = {
                        "Accept": "application/json",
                        "X-Authorization": authorization,
                    }
                    if body is not None:
                        headers.update({
                            "Content-Type": "application/json",
                            "Content-MD5": content_md5 or "",
                        })
                    if extra_headers:
                        headers.update(extra_headers)
                    try:
                        response = await client.request(
                            method,
                            f"{self.base_url}{path}",
                            params=params,
                            headers=headers,
                            content=body,
                        )
                    except httpx.HTTPError as exc:
                        raise TAUCError(f"Unable to reach TAUC: {exc}") from exc

                    try:
                        payload = response.json() if response.content else {}
                    except ValueError as exc:
                        raise TAUCError(
                            "TAUC returned invalid JSON "
                            f"(HTTP {response.status_code})"
                        ) from exc

                    if is_tauc_rate_limited(response.status_code, payload):
                        _tauc_cooldown_until = max(
                            _tauc_cooldown_until,
                            time.monotonic() + self.rate_limit_backoff,
                        )
                        if should_retry_tauc_request(
                            method,
                            response.status_code,
                            payload,
                            attempt,
                        ):
                            continue

                    if response.status_code >= 400 or (
                        isinstance(payload, dict)
                        and payload.get("errorCode") not in (None, 0, "0")
                    ):
                        raise TAUCError(tauc_error_message(
                            response.status_code,
                            method,
                            self.base_url,
                            path,
                            payload,
                            response.reason_phrase,
                        ))
                    return payload

        raise TAUCError("TAUC request could not be completed")

    async def get_device_id(self, serial_number: str, mac_address: str) -> str:
        payload = await self.request(
            "GET",
            settings.tauc_device_lookup_path,
            params={
                "sn": serial_number.strip(),
                "mac": compact_mac(mac_address),
            },
        )
        device_id = str(result_data(payload).get("deviceId") or "")
        if not device_id:
            raise TAUCError("TAUC did not return a device ID")
        return device_id

    async def device_info(self, device_id: str) -> Any:
        return await self.request(
            "GET",
            f"{settings.tauc_network_lookup_path.rstrip('/')}/{device_id}",
        )

    async def device_lookup(
        self,
        *,
        serial_number: str,
        mac_address: str | None = None,
    ) -> dict[str, Any]:
        if not mac_address:
            raise TAUCError("TAUC lookup requires serial number and MAC")
        device_id = await self.get_device_id(serial_number, mac_address)
        payload = await self.device_info(device_id)
        return {
            **result_data(payload),
            "deviceId": device_id,
            "sn": serial_number,
            "mac": compact_mac(mac_address),
        }

    async def network_lookup(
        self,
        *,
        serial_number: str,
        mac_address: str | None = None,
    ) -> dict[str, Any]:
        device = await self.device_lookup(
            serial_number=serial_number,
            mac_address=mac_address,
        )
        network_name = str(
            device.get("networkName") or device.get("network") or ""
        )
        network_id = str(
            device.get("networkId") or device.get("networkID") or ""
        )
        if not network_id and network_name:
            network_id = await self.network_id_by_name(network_name)
        if not network_id:
            resolved = await self.network_by_device(
                serial_number=serial_number,
                mac_address=mac_address or "",
            )
            network_id = resolved["networkId"]
            network_name = network_name or resolved["networkName"]
        return {
            "networkId": network_id,
            "networkName": network_name,
            "deviceId": device.get("deviceId"),
            "device": device,
        }

    async def network_id_by_name(self, network_name: str) -> str:
        name = network_name.strip()
        if not name:
            return ""
        payload = await self.request(
            "GET",
            settings.tauc_network_id_lookup_path,
            params={"networkName": name},
        )
        rows = extract_records(
            payload,
            {"result", "networks", "networkList"},
        )
        selected = next(
            (
                row
                for row in rows
                if str(row.get("networkName") or "").casefold()
                == name.casefold()
            ),
            rows[0] if rows else {},
        )
        return str(
            selected.get("networkId") or selected.get("id") or ""
        )

    async def network_by_device(
        self,
        *,
        serial_number: str = "",
        mac_address: str = "",
    ) -> dict[str, str]:
        serial = serial_number.strip()
        mac = compact_mac(mac_address)
        if not serial and not mac:
            return {"networkId": "", "networkName": ""}
        params = {"page": "1", "pageSize": "10"}
        if serial:
            params["sn"] = serial
        if mac:
            params["mac"] = mac
        payload = await self.request(
            "GET",
            settings.tauc_network_list_path,
            params=params,
        )
        rows = extract_records(
            payload,
            {"data", "result", "networks", "networkList"},
        )
        selected = rows[0] if rows else {}
        return {
            "networkId": str(
                selected.get("networkId") or selected.get("id") or ""
            ),
            "networkName": str(
                selected.get("networkName")
                or selected.get("network_name")
                or ""
            ),
        }

    async def wifi_ssid(self, device_id: str) -> Any:
        path = self._device_path(
            settings.tauc_wifi_ssid_read_path,
            device_id,
            "Wi-Fi SSID read endpoint",
        )
        return await self.request(
            "GET",
            path,
            params={"refresh": "true"},
        )

    async def wifi_password(self, device_id: str) -> Any:
        return await self.request(
            "GET",
            f"/v1/openapi/device-management/aginet/wifi-password/{device_id}",
            params={"refresh": "true"},
            extra_headers={
                "Required-Network-Control-Access": "false",
                "Disposable-Network-Control-Access": "true",
            },
        )

    def _resource_path(
        self,
        template: str,
        *,
        endpoint_name: str,
        device_id: str = "",
        network_id: str = "",
        fallback_identifier: str = "device_id",
    ) -> str:
        if not template:
            raise TAUCError(f"TAUC {endpoint_name} is not configured")

        path = template
        replaced = False
        for placeholder, identifier, label in (
            ("{device_id}", device_id, "device ID"),
            ("{deviceId}", device_id, "device ID"),
            ("{network_id}", network_id, "network ID"),
            ("{networkId}", network_id, "network ID"),
        ):
            if placeholder not in path:
                continue
            if not identifier:
                raise TAUCError(
                    f"TAUC {endpoint_name} requires a {label}, but TAUC did "
                    "not return one for this gateway"
                )
            path = path.replace(placeholder, identifier)
            replaced = True

        if "{" in path or "}" in path:
            raise TAUCError(
                f"TAUC {endpoint_name} contains an unsupported path placeholder"
            )

        if not replaced:
            identifier = (
                network_id
                if fallback_identifier == "network_id"
                else device_id
            )
            if not identifier:
                label = (
                    "network ID"
                    if fallback_identifier == "network_id"
                    else "device ID"
                )
                raise TAUCError(
                    f"TAUC {endpoint_name} requires a {label}, but TAUC did "
                    "not return one for this gateway"
                )
            path = f"{path.rstrip('/')}/{identifier}"
        return path

    def _device_path(
        self,
        template: str,
        device_id: str,
        endpoint_name: str,
    ) -> str:
        return self._resource_path(
            template,
            endpoint_name=endpoint_name,
            device_id=device_id,
        )

    def _control_path(self, template: str, device_id: str) -> str:
        return self._device_path(
            template,
            device_id,
            "control endpoint",
        )

    async def set_wifi_ssid(self, device_id: str, value: str) -> Any:
        path = self._control_path(
            settings.tauc_wifi_ssid_update_path,
            device_id,
        )
        return await self.request("PUT", path, json_data={"ssid": value})

    async def set_wifi_password(self, device_id: str, value: str) -> Any:
        path = self._control_path(
            settings.tauc_wifi_password_update_path,
            device_id,
        )
        return await self.request("PUT", path, json_data={"password": value})

    async def reboot(self, device_id: str) -> Any:
        path = self._control_path(settings.tauc_reboot_path, device_id)
        return await self.request("POST", path)

    async def connected_clients(
        self,
        device_id: str,
        network_id: str,
    ) -> Any:
        path = self._resource_path(
            settings.tauc_network_clients_path,
            endpoint_name="connected-device endpoint",
            device_id=device_id,
            network_id=network_id,
            fallback_identifier="network_id",
        )
        return await self.request("GET", path, params={"refresh": "true"})

    async def gateway_snapshot(
        self,
        device_id: str,
        *,
        network_id: str = "",
        network_name: str = "",
        serial_number: str = "",
        mac_address: str = "",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        device_payload = await self.device_info(device_id)
        device = result_data(device_payload)
        if not device and isinstance(device_payload, dict):
            device = device_payload
        network_id = network_id.strip() or str(
            device.get("networkId") or device.get("networkID") or ""
        )
        network_name = network_name.strip() or str(
            device.get("networkName") or device.get("network") or ""
        )
        resolution_errors: list[str] = []
        if not network_id and network_name:
            try:
                network_id = await self.network_id_by_name(network_name)
            except TAUCError as exc:
                resolution_errors.append(str(exc))
        if not network_id and (serial_number.strip() or mac_address.strip()):
            try:
                resolved = await self.network_by_device(
                    serial_number=serial_number,
                    mac_address=mac_address,
                )
                network_id = resolved["networkId"]
                network_name = network_name or resolved["networkName"]
            except TAUCError as exc:
                resolution_errors.append(str(exc))
        if not network_id:
            if resolution_errors:
                warnings.append(
                    "TAUC network ID resolution failed: "
                    + "; ".join(resolution_errors)
                )
            else:
                warnings.append(
                    "TAUC did not return a network ID; reassign this gateway "
                    "so the portal can resolve it from the saved serial and MAC."
                )

        embedded_clients = extract_records(device_payload, {
            "clients",
            "clientList",
            "connectedDevices",
            "connectedClients",
            "stations",
            "hosts",
        })

        wifi: dict[str, Any] = {}
        wifi_networks: list[dict[str, Any]] = []
        try:
            wifi_payload = await self.wifi_ssid(device_id)
            wifi = result_data(wifi_payload)
            if not wifi and isinstance(wifi_payload, dict):
                wifi = wifi_payload
            wifi_networks = extract_records(wifi_payload, {
                "result",
                "ssids",
                "ssidList",
                "wifiSsids",
                "wifiNetworks",
                "networks",
            })
            if not wifi_networks and any(
                key in wifi
                for key in ("ssid", "ssidName", "name", "wifiName")
            ):
                wifi_networks = [wifi]
        except TAUCError as exc:
            warnings.append(f"Wi-Fi data unavailable: {exc}")

        connected_devices = embedded_clients
        connected_devices_source = (
            "device_info" if embedded_clients else "unavailable"
        )
        if settings.tauc_network_clients_path:
            try:
                clients_payload = await self.connected_clients(
                    device_id,
                    network_id,
                )
                connected_devices = extract_records(clients_payload, {
                    "result",
                    "clients",
                    "clientList",
                    "networkClients",
                    "connectedDevices",
                    "connectedClients",
                    "stations",
                    "hosts",
                })
                connected_devices_source = "network_clients_endpoint"
            except TAUCError as exc:
                warnings.append(f"Connected-device data unavailable: {exc}")
        elif not embedded_clients:
            warnings.append(
                "Connected-device data was not included in device information; "
                "configure TAUC_NETWORK_CLIENTS_PATH for this tenant."
            )

        return {
            "device_id": device_id,
            "network_id": network_id or None,
            "network_name": network_name or None,
            "status": "partial" if warnings else "ready",
            "device": device,
            "wifi": wifi,
            "wifi_networks": wifi_networks,
            "connected_devices": connected_devices,
            "connected_devices_source": connected_devices_source,
            "connected_devices_endpoint_configured": bool(
                settings.tauc_network_clients_path
            ),
            "warnings": warnings,
        }

    async def diagnostics(self, device_id: str) -> Any:
        snapshot = await self.gateway_snapshot(device_id)
        snapshot["provider_diagnostics_configured"] = bool(
            settings.tauc_diagnostics_path
        )
        if settings.tauc_diagnostics_path:
            try:
                path = self._device_path(
                    settings.tauc_diagnostics_path,
                    device_id,
                    "diagnostics endpoint",
                )
                snapshot["provider_diagnostics"] = await self.request("GET", path)
            except TAUCError as exc:
                snapshot["warnings"].append(
                    f"Provider diagnostics unavailable: {exc}"
                )
                snapshot["status"] = "partial"
        return snapshot

    async def connection_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "configured": self.configured(),
            "connected": None,
            "base_url": self.base_url,
            "device_lookup_path": settings.tauc_device_lookup_path,
            "network_lookup_path": settings.tauc_network_lookup_path,
            "network_id_lookup_path": settings.tauc_network_id_lookup_path,
            "network_list_path": settings.tauc_network_list_path,
            "wifi_ssid_read_path": settings.tauc_wifi_ssid_read_path,
            "connected_devices_path": settings.tauc_network_clients_path or None,
            "diagnostics_path": settings.tauc_diagnostics_path or None,
            "minimum_request_interval_seconds": self.minimum_request_interval,
            "rate_limit_backoff_seconds": self.rate_limit_backoff,
            "snapshot_cache_seconds": settings.tauc_snapshot_cache_seconds,
            "authentication_mode": "mtls-aksk-x-authorization",
            "certificate_present": self.client_cert.is_file(),
            "private_key_present": self.client_key.is_file(),
            "access_key_configured": bool(self.access_key),
            "secret_key_configured": bool(self.secret_key),
        }
        if (
            self.configured()
            and settings.tauc_test_serial_number
            and settings.tauc_test_mac_address
        ):
            try:
                device = await self.device_lookup(
                    serial_number=settings.tauc_test_serial_number,
                    mac_address=settings.tauc_test_mac_address,
                )
                status.update({
                    "connected": True,
                    "device_id": device.get("deviceId"),
                    "network_id": device.get("networkId"),
                    "device_model": (
                        device.get("deviceModel") or device.get("model")
                    ),
                })
            except TAUCError as exc:
                status.update({"connected": False, "detail": str(exc)})
        else:
            status["detail"] = (
                "Set TAUC_TEST_SERIAL_NUMBER and TAUC_TEST_MAC_ADDRESS "
                "for a live lookup test"
            )
        return status
