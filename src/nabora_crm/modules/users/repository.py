import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from nabora_crm.modules.posts.models import Post
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.users.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email, or return None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch a user by ID, or return None if not found."""
    return db.query(User).filter(User.id == user_id).first()


def _user_conditions(
    *,
    search: str | None = None,
    role_id: uuid.UUID | None = None,
) -> list:
    conditions = []
    if role_id is not None:
        conditions.append(User.role_id == role_id)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(User.full_name.ilike(pattern), User.email.ilike(pattern))
        )
    return conditions


def list_users(
    db: Session,
    *,
    search: str | None = None,
    role_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> list[User]:
    """Return users matching the search and role filters, with pagination."""
    stmt = (
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(*_user_conditions(search=search, role_id=role_id))
        .options(selectinload(User.role))
        .order_by(User.full_name, User.email)
    )
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_users(
    db: Session,
    *,
    search: str | None = None,
    role_id: uuid.UUID | None = None,
) -> int:
    """Count users matching the search and role filters."""
    stmt = (
        select(func.count())
        .select_from(User)
        .join(Role, User.role_id == Role.id)
        .where(*_user_conditions(search=search, role_id=role_id))
    )
    return db.execute(stmt).scalar_one()


def get_posts_by_author_ids(
    db: Session, author_ids: list[uuid.UUID]
) -> list[Post]:
    """Return all posts authored by the given user IDs, newest first."""
    if not author_ids:
        return []
    stmt = (
        select(Post)
        .where(Post.author_id.in_(author_ids))
        .order_by(Post.updated_at.desc(), Post.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


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
