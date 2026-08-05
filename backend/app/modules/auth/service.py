from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_session_token, hash_password, verify_password
from app.core.settings import get_settings
from app.models.identity import AdminUser, Permission, Role

settings = get_settings()

DEFAULT_PERMISSIONS = {
    "command_post.view": "View NAB COMMAND POST",
    "customers.read": "View customer records",
    "customers.write": "Modify customer records",
    "billing.read": "View billing activity",
    "billing.write": "Modify billing operations",
    "wifi.read": "View TAUC managed WiFi",
    "wifi.write": "Modify TAUC managed WiFi",
    "network.read": "View network operations",
    "network.write": "Modify network operations",
    "audit.read": "View audit events",
    "admin.manage": "Manage administrators and roles",
    "field.read": "View assigned field operations",
    "field.write": "Update assigned field operations",
    "reports.read": "View operational reports",
    "portal.manage": "Manage customer portal configuration",
}

DEFAULT_ROLES = {
    "super_admin": list(DEFAULT_PERMISSIONS),
    "noc_operator": [
        "command_post.view",
        "customers.read",
        "wifi.read",
        "wifi.write",
        "network.read",
        "network.write",
        "audit.read",
        "reports.read",
    ],
    "billing": [
        "command_post.view",
        "customers.read",
        "billing.read",
        "billing.write",
    ],
    "support": [
        "command_post.view",
        "customers.read",
        "customers.write",
        "billing.read",
        "wifi.read",
        "network.read",
    ],
    "field_technician": [
        "command_post.view",
        "customers.read",
        "wifi.read",
        "network.read",
        "field.read",
        "field.write",
    ],
}


def bootstrap_identity(session: Session) -> None:
    permissions_by_code: dict[str, Permission] = {}

    for code, description in DEFAULT_PERMISSIONS.items():
        permission = session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            session.add(permission)
            session.flush()
        permissions_by_code[code] = permission

    roles_by_name: dict[str, Role] = {}

    for name, codes in DEFAULT_ROLES.items():
        role = session.scalar(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.name == name)
        )
        if role is None:
            role = Role(name=name, description=name.replace("_", " ").title())
            session.add(role)
            session.flush()

        role.permissions = [permissions_by_code[code] for code in codes]
        roles_by_name[name] = role

    admin = session.scalar(
        select(AdminUser)
        .options(selectinload(AdminUser.roles))
        .where(AdminUser.email == settings.bootstrap_admin_email.lower())
    )

    if admin is None:
        admin = AdminUser(
            email=settings.bootstrap_admin_email.lower(),
            display_name="NAB Administrator",
            password_hash=hash_password(settings.bootstrap_admin_password),
            is_active=True,
            is_superuser=True,
        )
        admin.roles = [roles_by_name["super_admin"]]
        session.add(admin)

    session.commit()


def authenticate(session: Session, email: str, password: str) -> AdminUser | None:
    user = session.scalar(
        select(AdminUser)
        .options(selectinload(AdminUser.roles).selectinload(Role.permissions))
        .where(AdminUser.email == email.lower())
    )

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def user_claims(user: AdminUser) -> tuple[list[str], list[str]]:
    roles = sorted({role.name for role in user.roles})
    permissions = sorted({
        permission.code
        for role in user.roles
        for permission in role.permissions
    })
    return roles, permissions


def issue_token(user: AdminUser) -> str:
    roles, permissions = user_claims(user)
    return create_session_token(
        subject=user.id,
        email=user.email,
        roles=roles,
        permissions=permissions,
    )
