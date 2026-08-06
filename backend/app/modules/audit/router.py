from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.observability import AuditEvent
from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/audit", tags=["audit"])



@router.get("")
def list_audit_events(
    claims: Annotated[dict, Depends(require_permission("audit.read"))],
    session: Annotated[Session, Depends(database_session)],
    method: str | None = None,
    actor_email: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[dict]:
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if method:
        statement = statement.where(AuditEvent.method == method.upper())
    if actor_email:
        statement = statement.where(AuditEvent.actor_email == actor_email.lower())
    rows = session.scalars(statement.limit(limit)).all()
    return [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "method": row.method,
            "path": row.path,
            "status_code": row.status_code,
            "ip_address": row.ip_address,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]
