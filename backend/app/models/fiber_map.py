from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uuid_string() -> str:
    return str(uuid4())


class FiberRouteGeometry(Base):
    __tablename__ = "fiber_route_geometries_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    route_id: Mapped[str] = mapped_column(
        ForeignKey("fiber_routes_v2.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    geometry_geojson: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="manual")
    updated_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
