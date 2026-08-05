from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.operations import SupportTicket
from app.modules.auth.dependencies import require_permission
from app.modules.tickets.schemas import TicketCreate, TicketRead, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])



@router.get("", response_model=list[TicketRead])
def list_tickets(
    claims: Annotated[dict, Depends(require_permission("customers.read"))],
    session: Annotated[Session, Depends(database_session)],
    ticket_status: str | None = Query(default=None, alias="status"),
    client_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SupportTicket]:
    statement = select(SupportTicket).order_by(SupportTicket.created_at.desc())

    if ticket_status:
        statement = statement.where(SupportTicket.status == ticket_status)

    if client_id:
        statement = statement.where(SupportTicket.client_id == client_id)

    return list(session.scalars(statement.limit(limit)).all())


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    payload: TicketCreate,
    claims: Annotated[dict, Depends(require_permission("customers.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> SupportTicket:
    ticket = SupportTicket(
        client_id=payload.client_id,
        subject=payload.subject,
        description=payload.description,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        created_by=str(claims.get("email") or "unknown"),
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    claims: Annotated[dict, Depends(require_permission("customers.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> SupportTicket:
    ticket = session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)

    session.commit()
    session.refresh(ticket)
    return ticket
