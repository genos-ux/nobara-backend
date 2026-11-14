import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from nabora_crm.modules.users.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email, or return None if not found."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch a user by ID."""
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_pending_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    role_id: uuid.UUID,
) -> User:
    """Create a new pending user with a placeholder password."""
    user = User(
        full_name=full_name,
        email=email,
        hashed_password="!pending",  # replaced on password setup
        role_id=role_id,
        is_active=True,
        is_pending=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
