import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.modules.posts.models import Post
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import (
    count_contributors,
    get_posts_by_author_ids,
    get_user_by_id,
    list_contributors as list_contributor_records,
)


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


def list_contributors(
    db: Session,
    *,
    search: str | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[tuple[User, list[Post]]], int]:
    """Return contributors paired with their posts, plus the total count."""
    contributors = list_contributor_records(
        db, search=search, offset=offset, limit=limit
    )
    posts_by_author: dict[uuid.UUID, list[Post]] = defaultdict(list)
    for post in get_posts_by_author_ids(db, [c.id for c in contributors]):
        posts_by_author[post.author_id].append(post)
    results = [(c, posts_by_author[c.id]) for c in contributors]
    return results, count_contributors(db, search=search)
