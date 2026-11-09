import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from nabora_crm.modules.posts.models import Post, PostSection, PostStatus


def _conditions(
    *,
    section: PostSection | None = None,
    status: PostStatus | None = None,
    author_id: uuid.UUID | None = None,
) -> list:
    conditions = []
    if section is not None:
        conditions.append(Post.section == section)
    if status is not None:
        conditions.append(Post.status == status)
    if author_id is not None:
        conditions.append(Post.author_id == author_id)
    return conditions


def create_post(
    db: Session,
    *,
    author_id: uuid.UUID,
    **fields,
) -> Post:
    """Create and persist a new post."""
    post = Post(author_id=author_id, **fields)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_post_by_id(db: Session, post_id: uuid.UUID) -> Post | None:
    """Fetch a post by ID, eager-loading its author."""
    stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.author))
    return db.execute(stmt).scalar_one_or_none()


def list_posts(
    db: Session,
    *,
    section: PostSection | None = None,
    status: PostStatus | None = None,
    author_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> list[Post]:
    """List posts with optional filters and pagination."""
    stmt = (
        select(Post)
        .where(*_conditions(section=section, status=status, author_id=author_id))
        .options(selectinload(Post.author))
        .order_by(Post.updated_at.desc(), Post.created_at.desc())
    )
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_posts(
    db: Session,
    *,
    section: PostSection | None = None,
    status: PostStatus | None = None,
    author_id: uuid.UUID | None = None,
) -> int:
    """Count posts matching the given filters."""
    stmt = (
        select(func.count())
        .select_from(Post)
        .where(*_conditions(section=section, status=status, author_id=author_id))
    )
    return db.execute(stmt).scalar_one()


def update_post(db: Session, post: Post, **fields) -> Post:
    """Apply field updates to a post and commit."""
    for field, value in fields.items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return post


def set_post_status(db: Session, post: Post, status: PostStatus) -> Post:
    """Update a post's status and commit."""
    post.status = status
    db.commit()
    db.refresh(post)
    return post


def delete_post(db: Session, post: Post) -> None:
    """Delete a post and commit."""
    db.delete(post)
    db.commit()
