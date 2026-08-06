from __future__ import annotations

import asyncio
import json
import os
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.settings import get_settings

settings = get_settings()


class MikroTikError(RuntimeError):
    pass


ROUTER_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class RouterProfile:
    key: str
    name: str
    site: str
    role: str
    base_url: str
    username: str
    password: str
    verify_tls: bool = True
    allow_insecure_http: bool = False
    ca_cert: str = ""
    timeout_seconds: float = 15.0
    poll_interval_seconds: float = 3.0
    enabled: bool = True

    def public_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "site": self.site,
            "role": self.role,
            "configured": bool(self.base_url and self.username and self.password),
            "enabled": self.enabled,
            "base_url": normalize_routeros_base_url(self.base_url) or None,
            "tls_verification": self.verify_tls,
            "ca_certificate_configured": bool(self.ca_cert),
            "poll_interval_seconds": self.poll_interval_seconds,
        }


def _boolean(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise MikroTikError(f"Invalid boolean value {value!r} in MikroTik router profile")


def _profile_from_mapping(row: dict[str, Any], index: int) -> RouterProfile:
    key = str(row.get("key") or "").strip().lower()
    if not ROUTER_KEY_PATTERN.fullmatch(key):
        raise MikroTikError(
            f"MikroTik router profile {index + 1} has invalid key {key!r}; "
            "use lowercase letters, numbers, underscores, or hyphens"
        )
    password = str(row.get("password") or "")
    password_env = str(row.get("password_env") or "").strip()
    if password_env:
        if not ENV_NAME_PATTERN.fullmatch(password_env):
            raise MikroTikError(
                f"MikroTik router profile {key!r} has an invalid password_env name"
            )
        password = os.getenv(password_env, "")
    try:
        timeout_seconds = max(1.0, min(60.0, float(
            row.get("timeout_seconds", settings.mikrotik_timeout_seconds)
        )))
        poll_interval_seconds = max(2.0, min(60.0, float(
            row.get(
                "poll_interval_seconds",
                settings.mikrotik_poll_interval_seconds,
            )
        )))
    except (TypeError, ValueError) as exc:
        raise MikroTikError(
            f"MikroTik router profile {key!r} has an invalid numeric setting"
        ) from exc
    return RouterProfile(
        key=key,
        name=str(row.get("name") or key).strip() or key,
        site=str(row.get("site") or "").strip(),
        role=str(row.get("role") or "infrastructure").strip(),
        base_url=str(row.get("base_url") or "").strip(),
        username=str(row.get("username") or "").strip(),
        password=password,
        verify_tls=_boolean(row.get("verify_tls"), True),
        allow_insecure_http=_boolean(row.get("allow_insecure_http"), False),
        ca_cert=str(row.get("ca_cert") or "").strip(),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        enabled=_boolean(row.get("enabled"), True),
    )


def legacy_router_profile() -> RouterProfile:
    return RouterProfile(
        key="default",
        name="Primary MikroTik",
        site="",
        role="infrastructure",
        base_url=settings.mikrotik_base_url,
        username=settings.mikrotik_username,
        password=settings.mikrotik_password,
        verify_tls=settings.mikrotik_verify_tls,
        allow_insecure_http=settings.mikrotik_allow_insecure_http,
        ca_cert=settings.mikrotik_ca_cert,
        timeout_seconds=settings.mikrotik_timeout_seconds,
        poll_interval_seconds=settings.mikrotik_poll_interval_seconds,
    )


def load_router_profiles(
    file_path: str | None = None,
    *,
    include_disabled: bool = False,
) -> list[RouterProfile]:
    configured_path = (
        settings.mikrotik_routers_file if file_path is None else file_path
    ).strip()
    source = Path(configured_path) if configured_path else None
    if source and source.is_file():
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MikroTikError(
                f"Unable to read MikroTik router profiles from {source}: {exc}"
            ) from exc
        rows = document.get("routers") if isinstance(document, dict) else document
        if not isinstance(rows, list):
            raise MikroTikError(
                "MikroTik routers file must contain a JSON list or an object "
                "with a routers list"
            )
        profiles = [
            _profile_from_mapping(row, index)
            for index, row in enumerate(rows)
            if isinstance(row, dict)
        ]
        keys = [profile.key for profile in profiles]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise MikroTikError(
                "Duplicate MikroTik router profile keys: " + ", ".join(duplicates)
            )
        return [
            profile
            for profile in profiles
            if include_disabled or profile.enabled
        ]
    profile = legacy_router_profile()
    return [profile] if include_disabled or profile.enabled else []


def router_profile(router_key: str) -> RouterProfile:
    normalized = router_key.strip().lower()
    for profile in load_router_profiles(include_disabled=True):
        if profile.key == normalized:
            return profile
    raise MikroTikError(f"Unknown MikroTik router profile {router_key!r}")


def normalize_routeros_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if not base_url:
        return ""
    if not base_url.lower().startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    if not base_url.lower().endswith("/rest"):
        base_url = f"{base_url}/rest"
    return base_url


def routeros_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [payload]
    return []


def first_record(payload: Any) -> dict[str, Any]:
    records = routeros_records(payload)
    return records[0] if records else {}


def routeros_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def memory_utilization(resource: dict[str, Any]) -> float | None:
    total = routeros_number(resource.get("total-memory"))
    free = routeros_number(resource.get("free-memory"))
    if total is None or free is None or total <= 0:
        return None
    return round(max(0.0, min(100.0, (total - free) / total * 100.0)), 2)


def normalize_mac(value: Any) -> str:
    compact = "".join(
        character for character in str(value or "").upper()
        if character.isalnum()
    )
    if len(compact) != 12:
        return str(value or "").upper()
    return ":".join(compact[index:index + 2] for index in range(0, 12, 2))


def merge_network_neighbors(
    leases: list[dict[str, Any]],
    arp_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    neighbors: dict[str, dict[str, Any]] = {}

    def key_for(row: dict[str, Any], prefix: str) -> str:
        mac = normalize_mac(row.get("mac-address") or row.get("mac"))
        address = str(row.get("address") or row.get("ip") or "")
        return mac or address or f"{prefix}:{len(neighbors)}"

    for lease in leases:
        mac = normalize_mac(lease.get("mac-address"))
        address = str(lease.get("address") or "")
        key = key_for(lease, "lease")
        neighbors[key] = {
            "id": key,
            "hostname": str(
                lease.get("host-name")
                or lease.get("comment")
                or lease.get("client-id")
                or ""
            ),
            "mac_address": mac,
            "ip_address": address,
            "interface": str(
                lease.get("server")
                or lease.get("interface")
                or ""
            ),
            "status": str(lease.get("status") or "leased"),
            "active": str(lease.get("status") or "").lower() == "bound",
            "last_seen": str(lease.get("last-seen") or ""),
            "source": "dhcp",
            "lease": lease,
            "arp": None,
        }

    for arp in arp_entries:
        key = key_for(arp, "arp")
        existing = neighbors.get(key)
        if existing is None:
            existing = {
                "id": key,
                "hostname": str(arp.get("comment") or ""),
                "mac_address": normalize_mac(arp.get("mac-address")),
                "ip_address": str(arp.get("address") or ""),
                "interface": str(arp.get("interface") or ""),
                "status": "reachable" if str(arp.get("complete", "true")).lower() == "true" else "incomplete",
                "active": str(arp.get("complete", "true")).lower() == "true",
                "last_seen": "",
                "source": "arp",
                "lease": None,
                "arp": arp,
            }
            neighbors[key] = existing
        else:
            existing["arp"] = arp
            existing["source"] = "dhcp+arp"
            existing["active"] = existing["active"] or (
                str(arp.get("complete", "true")).lower() == "true"
            )
            existing["interface"] = (
                existing["interface"] or str(arp.get("interface") or "")
            )
            existing["ip_address"] = (
                existing["ip_address"] or str(arp.get("address") or "")
            )

    return sorted(
        neighbors.values(),
        key=lambda row: (
            not bool(row["active"]),
            str(row["hostname"]).lower(),
            str(row["ip_address"]),
        ),
    )


class MikroTikClient:
    def __init__(self, profile: RouterProfile | None = None) -> None:
        self.profile = profile or legacy_router_profile()
        self.base_url = normalize_routeros_base_url(self.profile.base_url)
        self.username = self.profile.username.strip()
        self.password = self.profile.password
        self.verify_tls = self.profile.verify_tls
        self.allow_insecure_http = self.profile.allow_insecure_http
        self.ca_cert = self.profile.ca_cert.strip()
        self.timeout = self.profile.timeout_seconds

    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _tls_verification(self) -> bool | ssl.SSLContext:
        if not self.verify_tls:
            return False
        if not self.ca_cert:
            return True
        certificate = Path(self.ca_cert)
        if not certificate.is_file():
            raise MikroTikError(
                "MIKROTIK_CA_CERT does not point to a readable CA certificate"
            )
        return ssl.create_default_context(cafile=str(certificate))

    async def get(self, path: str) -> Any:
        if not self.configured():
            raise MikroTikError(
                "MikroTik is not configured; set MIKROTIK_BASE_URL, "
                "MIKROTIK_USERNAME, and MIKROTIK_PASSWORD"
            )
        if (
            self.base_url.lower().startswith("http://")
            and not self.allow_insecure_http
        ):
            raise MikroTikError(
                "Refusing to send RouterOS credentials over HTTP. Configure "
                "HTTPS or explicitly set MIKROTIK_ALLOW_INSECURE_HTTP=true "
                "for a temporary isolated lab."
            )
        resource_path = "/" + path.strip("/")
        url = f"{self.base_url}{resource_path}"
        try:
            async with httpx.AsyncClient(
                auth=httpx.BasicAuth(self.username, self.password),
                verify=self._tls_verification(),
                timeout=self.timeout,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except MikroTikError:
            raise
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                detail = "authentication failed; verify the RouterOS username and password"
            elif code == 403:
                detail = (
                    "access denied; grant the RouterOS user read and rest-api policies"
                )
            elif code == 404:
                detail = (
                    f"RouterOS REST resource {resource_path} was not found; "
                    "verify RouterOS v7 and the www-ssl REST service"
                )
            else:
                message = exc.response.text[:240].replace("\n", " ")
                detail = f"HTTP {code}: {message or exc.response.reason_phrase}"
            raise MikroTikError(f"MikroTik {detail}") from exc
        except httpx.ConnectError as exc:
            raise MikroTikError(
                "Unable to connect to MikroTik RouterOS; verify the base URL, "
                "routing, firewall, and www-ssl service"
            ) from exc
        except httpx.TimeoutException as exc:
            raise MikroTikError(
                f"MikroTik request timed out after {self.timeout:g} seconds"
            ) from exc
        except httpx.TransportError as exc:
            raise MikroTikError(
                f"MikroTik TLS or network connection failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise MikroTikError("MikroTik returned invalid JSON") from exc

    async def records(self, path: str) -> list[dict[str, Any]]:
        return routeros_records(await self.get(path))

    async def connection_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "service": "mikrotik",
            "key": self.profile.key,
            "name": self.profile.name,
            "site": self.profile.site,
            "role": self.profile.role,
            "configured": self.configured(),
            "connected": False,
            "base_url": self.base_url or None,
            "authentication_mode": "HTTP Basic",
            "tls_verification": self.verify_tls,
            "secure_transport": self.base_url.lower().startswith("https://"),
            "ca_certificate_configured": bool(self.ca_cert),
            "mode": "read-only",
        }
        if not self.configured():
            status["detail"] = (
                "Set MIKROTIK_BASE_URL, MIKROTIK_USERNAME, and "
                "MIKROTIK_PASSWORD in the server .env file."
            )
            return status
        try:
            identity = first_record(await self.get("/system/identity"))
            status.update(
                connected=True,
                path="/system/identity",
                identity=identity.get("name") or "RouterOS",
            )
        except MikroTikError as exc:
            status["detail"] = str(exc)
        return status

    async def snapshot(self) -> dict[str, Any]:
        resources = {
            "identity": "/system/identity",
            "resource": "/system/resource",
            "interfaces": "/interface",
            "addresses": "/ip/address",
            "routes": "/ip/route",
            "dhcp_leases": "/ip/dhcp-server/lease",
            "arp": "/ip/arp",
        }
        responses = await asyncio.gather(
            *(self.get(path) for path in resources.values()),
            return_exceptions=True,
        )
        data: dict[str, Any] = {}
        warnings: list[str] = []
        for (name, path), response in zip(resources.items(), responses):
            if isinstance(response, Exception):
                data[name] = {} if name in {"identity", "resource"} else []
                warnings.append(f"{path}: {response}")
            elif name in {"identity", "resource"}:
                data[name] = first_record(response)
            else:
                data[name] = routeros_records(response)

        resource = data["resource"]
        interfaces = data["interfaces"]
        leases = data["dhcp_leases"]
        arp_entries = data["arp"]
        network_neighbors = merge_network_neighbors(leases, arp_entries)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "ready" if not warnings else "partial",
            "mode": "read-only",
            "scope": "internal-network-operations",
            "customer_assignment_supported": False,
            "identity": data["identity"],
            "resource": resource,
            "summary": {
                "router_name": data["identity"].get("name"),
                "platform": resource.get("platform"),
                "board_name": resource.get("board-name"),
                "version": resource.get("version"),
                "uptime": resource.get("uptime"),
                "cpu_load_percent": routeros_number(resource.get("cpu-load")),
                "memory_used_percent": memory_utilization(resource),
                "interfaces": len(interfaces),
                "interfaces_running": sum(
                    str(row.get("running", "")).lower() == "true"
                    for row in interfaces
                ),
                "dhcp_leases": len(leases),
                "dhcp_bound": sum(
                    str(row.get("status", "")).lower() == "bound"
                    for row in leases
                ),
                "observed_hosts": len(network_neighbors),
                "routes": len(data["routes"]),
            },
            "interfaces": interfaces,
            "addresses": data["addresses"],
            "routes": data["routes"],
            "dhcp_leases": leases,
            "arp": arp_entries,
            "network_neighbors": network_neighbors,
            "warnings": warnings,
        }
