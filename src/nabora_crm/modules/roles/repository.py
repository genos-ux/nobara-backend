import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from nabora_crm.modules.roles.models import Permission, Role, role_permissions


def get_role_by_id(db: Session, role_id: uuid.UUID) -> Role | None:
    """Fetch a role by ID, or return None if not found."""
    stmt = select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
    return db.execute(stmt).scalar_one_or_none()


def get_role_by_name(db: Session, name: str) -> Role | None:
    """Fetch a role by name, or return None if not found."""
    stmt = select(Role).where(Role.name == name).options(selectinload(Role.permissions))
    return db.execute(stmt).scalar_one_or_none()


def get_all_roles(db: Session) -> list[Role]:
    """Return all roles, eager-loading permissions."""
    stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    return list(db.execute(stmt).scalars().all())


def get_all_permissions(db: Session) -> list[Permission]:
    """Return all permissions."""
    stmt = select(Permission).order_by(Permission.name)
    return list(db.execute(stmt).scalars().all())


def get_permission_by_name(db: Session, name: str) -> Permission | None:
    """Fetch a permission by name, or return None if not found."""
    return db.execute(
        select(Permission).where(Permission.name == name)
    ).scalar_one_or_none()


def get_permissions_by_names(db: Session, names: list[str]) -> list[Permission]:
    """Fetch all permissions matching the given names."""
    if not names:
        return []
    stmt = select(Permission).where(Permission.name.in_(names))
    return list(db.execute(stmt).scalars().all())


def create_role(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    is_system: bool = False,
    permissions: list[Permission] | None = None,
) -> Role:
    """Create a new role and commit."""
    role = Role(
        name=name,
        description=description,
        is_system=is_system,
    )
    if permissions:
        role.permissions = permissions
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(
    db: Session,
    role: Role,
    *,
    name: str | None = None,
    description: str | None = None,
    permissions: list[Permission] | None = None,
) -> Role:
    """Update a role's fields and commit."""
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if permissions is not None:
        role.permissions = permissions
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role: Role) -> None:
    """Delete a role. Callers should check is_system before calling."""
    db.delete(role)
    db.commit()


def create_permission(db: Session, name: str) -> Permission:
    """Create a new permission and commit."""
    perm = Permission(name=name)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def get_user_permissions(db: Session, role_id: uuid.UUID) -> list[str]:
    """Return the list of permission names for the role assigned to a user."""
    stmt = (
        select(Permission.name)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .where(role_permissions.c.role_id == role_id)
    )
    return list(db.execute(stmt).scalars().all())
