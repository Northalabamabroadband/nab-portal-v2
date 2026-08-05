from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_string() -> str:
    return str(uuid4())


class FiberAsset(Base):
    __tablename__ = "fiber_assets_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    asset_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    asset_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    location_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    parent_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    strand_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_capacity: Mapped[int] = mapped_column(Integer, default=0)
    total_capacity: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FiberRoute(Base):
    __tablename__ = "fiber_routes_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    route_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    status: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    cable_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    strand_count: Mapped[int] = mapped_column(Integer, default=0)
    length_feet: Mapped[float] = mapped_column(Float, default=0)
    start_location: Mapped[str | None] = mapped_column(String(220), nullable=True)
    end_location: Mapped[str | None] = mapped_column(String(220), nullable=True)
    ownership: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
