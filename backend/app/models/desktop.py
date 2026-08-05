from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DesktopOutage(Base):
    __tablename__ = "desktop_outages_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_key: Mapped[str] = mapped_column(
        String(160),
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(
        String(32),
        default="investigating",
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        default="warning",
        index=True,
    )
    affected_area: Mapped[str] = mapped_column(String(500), default="")
    affected_services: Mapped[str] = mapped_column(
        String(500),
        default="Internet service",
    )
    public_message: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
