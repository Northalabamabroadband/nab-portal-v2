from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_session_token

bearer = HTTPBearer(auto_error=False)


def current_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    token = credentials.credentials if credentials else request.cookies.get("nab_v2_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        return decode_session_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc


def require_permission(permission: str):
    def dependency(claims: Annotated[dict, Depends(current_claims)]) -> dict:
        permissions = claims.get("permissions", [])
        roles = claims.get("roles", [])

        if "super_admin" not in roles and permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )

        return claims

    return dependency
