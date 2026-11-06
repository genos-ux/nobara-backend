import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import USERS_READ, USERS_WRITE
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.users.schemas import UserOut
from nabora_crm.modules.users.service import get_user_or_404, set_user_active

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_READ)),
) -> UserOut:
    """Get a single user by ID."""
    user = get_user_or_404(db, user_id)
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Deactivate a user account. The user can no longer authenticate."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=False)
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )


@router.patch("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Reactivate a previously deactivated user account."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=True)
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )
