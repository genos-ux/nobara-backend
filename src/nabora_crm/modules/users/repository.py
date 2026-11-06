import uuid

from sqlalchemy.orm import Session

from nabora_crm.modules.users.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email, or return None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch a user by ID, or return None if not found."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    role_id: uuid.UUID,
    is_active: bool = True,
) -> User:
    """Create and commit a new user. Rolls back on error."""
    user = User(
        email=email,
        hashed_password=hashed_password,
        role_id=role_id,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user
