from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def uuid_string() -> str:
    return str(uuid4())


class AdminUser(Base):
    __tablename__ = "admin_users_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    roles: Mapped[list["Role"]] = relationship(
        secondary="admin_user_roles_v2",
        back_populates="users",
    )


class Role(Base):
    __tablename__ = "admin_roles_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")

    users: Mapped[list[AdminUser]] = relationship(
        secondary="admin_user_roles_v2",
        back_populates="roles",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="admin_role_permissions_v2",
        back_populates="roles",
    )


class Permission(Base):
    __tablename__ = "admin_permissions_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")

    roles: Mapped[list[Role]] = relationship(
        secondary="admin_role_permissions_v2",
        back_populates="permissions",
    )


class UserRole(Base):
    __tablename__ = "admin_user_roles_v2"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("admin_users_v2.id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("admin_roles_v2.id"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "admin_role_permissions_v2"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id: Mapped[str] = mapped_column(ForeignKey("admin_roles_v2.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("admin_permissions_v2.id"), primary_key=True)
