from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.settings import get_settings

settings = get_settings()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_session_token(
    *,
    subject: str,
    email: str,
    roles: list[str],
    permissions: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=settings.session_ttl_seconds)

    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "roles": roles,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": "nab-portal-v2",
        "aud": "nab-command-post",
    }

    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.app_secret_key,
        algorithms=["HS256"],
        audience="nab-command-post",
        issuer="nab-portal-v2",
    )
