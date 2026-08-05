from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import database_session
from app.models.operations import CustomerTaucAssignment
from app.modules.auth.dependencies import require_permission
from app.modules.tauc.client import TAUCClient, TAUCError, compact_mac
from app.modules.tauc.schemas import GatewayMappingRequest

router = APIRouter(prefix="/customers", tags=["customers", "tauc"])


@router.get("/{client_id}/gateways")
def customer_gateways(
    client_id: str,
    claims: Annotated[dict, Depends(require_permission("customers.read"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    assignments = list(session.scalars(
        select(CustomerTaucAssignment)
        .where(CustomerTaucAssignment.client_id == client_id)
        .order_by(CustomerTaucAssignment.created_at.asc())
    ).all())
    return {
        "client_id": client_id,
        "devices": [assignment.as_dict() for assignment in assignments],
    }


@router.post("/{client_id}/gateway/resolve")
async def resolve_customer_gateway(
    client_id: str,
    payload: GatewayMappingRequest,
    claims: Annotated[dict, Depends(require_permission("customers.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    if payload.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path client ID and payload client ID do not match",
        )

    tauc = TAUCClient()
    try:
        device = await tauc.device_lookup(
            serial_number=payload.serial_number,
            mac_address=payload.mac_address,
        )
    except TAUCError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    device_id = str(device.get("deviceId") or "").strip()
    serial_number = str(device.get("sn") or payload.serial_number).strip()
    mac_address = compact_mac(str(device.get("mac") or payload.mac_address or ""))
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TAUC did not return a device ID",
        )

    matches = [CustomerTaucAssignment.tauc_device_id == device_id]
    if serial_number:
        matches.append(CustomerTaucAssignment.serial_number == serial_number)
    if mac_address:
        matches.append(CustomerTaucAssignment.mac_address == mac_address)
    assignment = session.scalar(
        select(CustomerTaucAssignment).where(or_(*matches))
    )
    if assignment is not None and assignment.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This TAUC device is already assigned to another customer",
        )

    actor = str(claims.get("email") or claims.get("sub") or "unknown")
    created = assignment is None
    if assignment is None:
        assignment = CustomerTaucAssignment(
            client_id=client_id,
            tauc_device_id=device_id,
            serial_number=serial_number,
            mac_address=mac_address or None,
            assigned_by=actor,
        )
        session.add(assignment)

    assignment.device_model = str(
        device.get("deviceModel") or device.get("model") or ""
    ) or None
    assignment.network_id = str(
        device.get("networkId") or device.get("networkID") or ""
    ) or None
    assignment.network_name = str(
        device.get("networkName") or device.get("network") or ""
    ) or None
    assignment.firmware_version = str(
        device.get("fwVersion") or device.get("firmwareVersion") or ""
    ) or None
    assignment.assigned_by = actor

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This TAUC device is already assigned",
        ) from exc
    session.refresh(assignment)

    return {
        "client_id": client_id,
        "assignment": assignment.as_dict(),
        "device": device,
        "network": {
            "networkId": assignment.network_id,
            "networkName": assignment.network_name,
            "deviceId": assignment.tauc_device_id,
        },
        "resolved": True,
        "created": created,
    }


@router.delete("/{client_id}/gateways/{assignment_id}", status_code=204)
def remove_customer_gateway(
    client_id: str,
    assignment_id: str,
    claims: Annotated[dict, Depends(require_permission("customers.write"))],
    session: Annotated[Session, Depends(database_session)],
) -> None:
    assignment = session.scalar(
        select(CustomerTaucAssignment).where(
            CustomerTaucAssignment.id == assignment_id,
            CustomerTaucAssignment.client_id == client_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer TAUC device assignment not found",
        )
    session.delete(assignment)
    session.commit()
