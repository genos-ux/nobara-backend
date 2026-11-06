import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import ROLES_WRITE, ROLES_READ, ROLES_DELETE
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.roles.schemas import (
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
)
from nabora_crm.modules.roles.service import (
    create_role_with_permissions,
    get_role_or_404,
    list_permissions,
    list_roles,
    remove_role,
    update_role_with_permissions,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def get_roles(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(ROLES_READ)),
) -> list[RoleOut]:
    """List all roles with their permissions."""
    roles = list_roles(db)
    return [
        RoleOut(
            id=r.id,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=[
                PermissionOut(id=p.id, name=p.name) for p in r.permissions
            ],
        )
        for r in roles
    ]


@router.post("", response_model=RoleOut, status_code=201)
def post_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(ROLES_WRITE)),
) -> RoleOut:
    """Create a new role with the given permissions."""
    role = create_role_with_permissions(
        db,
        name=body.name,
        description=body.description,
        permission_names=body.permission_names,
    )
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            PermissionOut(id=p.id, name=p.name) for p in role.permissions
        ],
    )


@router.put("/{role_id}", response_model=RoleOut)
def put_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(ROLES_WRITE)),
) -> RoleOut:
    """Update a role's fields and/or permissions."""
    role = get_role_or_404(db, role_id)
    role = update_role_with_permissions(
        db,
        role,
        name=body.name,
        description=body.description,
        permission_names=body.permission_names,
    )
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            PermissionOut(id=p.id, name=p.name) for p in role.permissions
        ],
    )


@router.delete("/{role_id}", status_code=204)
def delete_role_endpoint(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(ROLES_DELETE)),
) -> None:
    """Delete a non-system role."""
    role = get_role_or_404(db, role_id)
    remove_role(db, role)


@router.get("/permissions", response_model=list[PermissionOut])
def get_permissions(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(ROLES_READ)),
) -> list[PermissionOut]:
    """List all available permissions."""
    perms = list_permissions(db)
    return [PermissionOut(id=p.id, name=p.name) for p in perms]
