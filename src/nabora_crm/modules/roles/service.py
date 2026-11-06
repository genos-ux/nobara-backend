import uuid

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.roles.repository import (
    create_role,
    delete_role,
    get_all_permissions,
    get_all_roles,
    get_permission_by_name,
    get_permissions_by_names,
    get_role_by_id,
    get_role_by_name,
    update_role,
)


def list_roles(db: Session) -> list[Role]:
    """Return all roles."""
    return get_all_roles(db)


def list_permissions(db: Session):
    """Return all permissions."""
    return get_all_permissions(db)


def get_role_or_404(db: Session, role_id: uuid.UUID) -> Role:
    """Fetch a role by ID or raise DomainError."""
    role = get_role_by_id(db, role_id)
    if role is None:
        raise DomainError(f"Role with id {role_id} not found")
    return role


def create_role_with_permissions(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    permission_names: list[str],
) -> Role:
    """Create a new role with the given permissions."""
    existing = get_role_by_name(db, name)
    if existing:
        raise DomainError(f"Role '{name}' already exists")

    _validate_permission_names(db, permission_names)

    permissions = get_permissions_by_names(db, permission_names)
    return create_role(
        db,
        name=name,
        description=description,
        is_system=False,
        permissions=permissions,
    )


def update_role_with_permissions(
    db: Session,
    role: Role,
    *,
    name: str | None = None,
    description: str | None = None,
    permission_names: list[str] | None = None,
) -> Role:
    """Update a role's fields and/or permissions."""
    if name is not None and name != role.name:
        existing = get_role_by_name(db, name)
        if existing:
            raise DomainError(f"Role '{name}' already exists")

    if permission_names is not None:
        _validate_permission_names(db, permission_names)

    permissions = None
    if permission_names is not None:
        permissions = get_permissions_by_names(db, permission_names)

    return update_role(
        db,
        role,
        name=name,
        description=description,
        permissions=permissions,
    )


def remove_role(db: Session, role: Role) -> None:
    """Delete a non-system role."""
    if role.is_system:
        raise DomainError("System roles cannot be deleted")
    delete_role(db, role)


def _validate_permission_names(db: Session, names: list[str]) -> None:
    """Ensure all permission names exist in the database."""
    for name in names:
        if get_permission_by_name(db, name) is None:
            raise DomainError(f"Permission '{name}' does not exist")
