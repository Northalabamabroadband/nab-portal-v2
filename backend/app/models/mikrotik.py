from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MikroTikInterfaceRollup(Base):
    __tablename__ = "mikrotik_interface_rollups_v2"
    __table_args__ = (
        UniqueConstraint(
            "router_key",
            "interface_name",
            "bucket_start",
            name="uq_mikrotik_rollup_router_interface_bucket",
        ),
        Index(
            "ix_mikrotik_rollup_router_bucket",
            "router_key",
            "bucket_start",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    router_key: Mapped[str] = mapped_column(String(64), index=True)
    interface_name: Mapped[str] = mapped_column(String(160), index=True)
    bucket_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    rx_average_bps: Mapped[float] = mapped_column(Float, default=0.0)
    tx_average_bps: Mapped[float] = mapped_column(Float, default=0.0)
    rx_peak_bps: Mapped[float] = mapped_column(Float, default=0.0)
    tx_peak_bps: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
