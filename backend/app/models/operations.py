from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_string() -> str:
    return str(uuid4())


class SupportTicket(Base):
    __tablename__ = "support_tickets_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    subject: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_by: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkOrder(Base):
    __tablename__ = "work_orders_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    assigned_technician: Mapped[str | None] = mapped_column(String(320), nullable=True)
    service_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InventoryItem(Base):
    __tablename__ = "inventory_items_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    sku: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(120), default="General")
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str | None] = mapped_column(String(220), nullable=True)
    serial_tracking: Mapped[str] = mapped_column(String(16), default="optional")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerNote(Base):
    __tablename__ = "customer_notes_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    body: Mapped[str] = mapped_column(Text)
    author_email: Mapped[str] = mapped_column(String(320), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomerTaucAssignment(Base):
    __tablename__ = "customer_tauc_assignments_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    tauc_device_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    network_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    network_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(160), nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(320), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "device_id": self.tauc_device_id,
            "serial_number": self.serial_number,
            "mac_address": self.mac_address,
            "device_model": self.device_model,
            "network_id": self.network_id,
            "network_name": self.network_name,
            "firmware_version": self.firmware_version,
            "assigned_by": self.assigned_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
