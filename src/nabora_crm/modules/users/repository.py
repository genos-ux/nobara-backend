from sqlalchemy.orm import Session

from nabora_crm.modules.users.models import Role, User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email, or return None if not found."""
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    role: Role,
    is_active: bool = True,
) -> User:
    """Create and commit a new user. Rolls back on error."""
    user = User(
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user
