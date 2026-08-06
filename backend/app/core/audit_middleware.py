from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.database import SessionLocal
from app.core.security import decode_session_token
from app.models.observability import AuditEvent


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        path = request.url.path
        v2_auditable = (
            path.startswith("/api/v2/")
            and not path.startswith("/api/v2/live/")
            and path not in {"/api/v2/audit", "/api/v2/auth/login"}
        )
        desktop_auditable = path.startswith("/api/desktop/v1/")
        if v2_auditable or desktop_auditable:
            token = request.headers.get("authorization", "")
            if token.lower().startswith("bearer "):
                token = token[7:]
            else:
                token = request.cookies.get("nab_v2_session", "")

            claims = {}
            if token:
                try:
                    claims = decode_session_token(token)
                except Exception:
                    claims = {}

            try:
                with SessionLocal() as session:
                    session.add(AuditEvent(
                        actor_id=str(claims.get("sub") or "") or None,
                        actor_email=(
                            "desktop-sync"
                            if desktop_auditable
                            else str(claims.get("email") or "") or None
                        ),
                        action=f"{request.method} {path}",
                        resource_type="http_request",
                        method=request.method,
                        path=path,
                        status_code=response.status_code,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        detail=request.url.query or "",
                    ))
                    session.commit()
            except Exception:
                # Auditing must never break the operational request.
                pass

        return response
