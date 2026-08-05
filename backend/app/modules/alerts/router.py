from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.observability import OperationalAlert
from app.modules.alerts.schemas import AlertCreate, AlertRead
from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/alerts", tags=["alerts"])



@router.get("", response_model=list[AlertRead])
def list_alerts(
    claims: Annotated[dict, Depends(require_permission("network.read"))],
    session: Annotated[Session, Depends(database_session)],
    acknowledged: bool = False,
    severity: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[OperationalAlert]:
    statement = (
        select(OperationalAlert)
        .where(OperationalAlert.acknowledged.is_(acknowledged))
        .order_by(OperationalAlert.created_at.desc())
    )
    if severity:
        statement = statement.where(OperationalAlert.severity == severity)
    return list(session.scalars(statement.limit(limit)).all())


@router.post("", response_model=AlertRead, status_code=201)
def create_alert(
    payload: AlertCreate,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> OperationalAlert:
    alert = OperationalAlert(**payload.model_dump())
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: str,
    claims: Annotated[dict, Depends(require_permission("network.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> OperationalAlert:
    alert = session.get(OperationalAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.acknowledged = True
    alert.acknowledged_by = str(claims.get("email") or claims.get("sub") or "administrator")
    alert.acknowledged_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(alert)
    return alert
