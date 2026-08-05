from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.identity import AdminUser, Permission, Role
from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/admin", tags=["administration"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class UserAccessUpdate(BaseModel):
    role_names: list[str] | None = None
    is_active: bool | None = None


class RoleAccessUpdate(BaseModel):
    permission_codes: list[str]


@router.get("/access")
def access_inventory(
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    users = list(session.scalars(
        select(AdminUser).options(selectinload(AdminUser.roles)).order_by(AdminUser.email)
    ).all())
    roles = list(session.scalars(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    ).all())
    permissions = list(session.scalars(select(Permission).order_by(Permission.code)).all())
    return {
        "users": [{
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "roles": sorted(role.name for role in user.roles),
        } for user in users],
        "roles": [{
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": sorted(permission.code for permission in role.permissions),
        } for role in roles],
        "permissions": [{"code": p.code, "description": p.description} for p in permissions],
    }


@router.patch("/users/{user_id}")
def update_user_access(
    user_id: str,
    payload: UserAccessUpdate,
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    user = session.scalar(
        select(AdminUser).options(selectinload(AdminUser.roles)).where(AdminUser.id == user_id)
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found")
    if payload.role_names is not None:
        names = sorted(set(payload.role_names))
        roles = list(session.scalars(select(Role).where(Role.name.in_(names))).all()) if names else []
        if len(roles) != len(names):
            raise HTTPException(status_code=400, detail="One or more roles are invalid")
        user.roles = roles
    if payload.is_active is not None:
        if user.email == claims.get("email") and not payload.is_active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        user.is_active = payload.is_active
    session.commit()
    return {"id": user.id, "email": user.email, "is_active": user.is_active, "roles": sorted(r.name for r in user.roles)}


@router.patch("/roles/{role_id}")
def update_role_access(
    role_id: str,
    payload: RoleAccessUpdate,
    claims: Annotated[dict, Depends(require_permission("admin.manage"))],
    session: Annotated[Session, Depends(database_session)],
) -> dict:
    role = session.scalar(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    codes = sorted(set(payload.permission_codes))
    permissions = list(session.scalars(select(Permission).where(Permission.code.in_(codes))).all()) if codes else []
    if len(permissions) != len(codes):
        raise HTTPException(status_code=400, detail="One or more permissions are invalid")
    role.permissions = permissions
    session.commit()
    return {"id": role.id, "name": role.name, "permissions": sorted(p.code for p in role.permissions)}
