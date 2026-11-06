import uuid

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_id


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    """Fetch a user by ID or raise DomainError."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise DomainError(f"User with id {user_id} not found")
    return user


def set_user_active(db: Session, user: User, is_active: bool) -> User:
    """Activate or deactivate a user and commit."""
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
