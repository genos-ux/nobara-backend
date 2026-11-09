import uuid

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.core.permissions import POSTS_REVIEW
from nabora_crm.modules.posts.models import Post, PostSection, PostStatus
from nabora_crm.modules.posts.repository import (
    count_posts,
    create_post as create_post_record,
    delete_post as delete_post_record,
    get_post_by_id,
    list_posts as list_post_records,
    set_post_status,
    update_post as update_post_record,
)
from nabora_crm.modules.posts.schemas import PostCreate, PostUpdate
from nabora_crm.modules.roles.repository import get_user_permissions
from nabora_crm.modules.users.models import User


def _has_permission(db: Session, user: User, permission: str) -> bool:
    return permission in set(get_user_permissions(db, user.role_id))


def _can_review(db: Session, user: User) -> bool:
    return _has_permission(db, user, POSTS_REVIEW)


def _dump_post_data(payload: PostCreate | PostUpdate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if data.get("image_url") is not None:
        data["image_url"] = str(data["image_url"])
    return data


def create_post(db: Session, *, user: User, payload: PostCreate) -> Post:
    """Create a new post authored by the current user."""
    return create_post_record(
        db,
        author_id=user.id,
        **_dump_post_data(payload),
    )


def list_posts(
    db: Session,
    *,
    user: User,
    section: PostSection | None = None,
    status: PostStatus | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[Post], int]:
    """List posts visible to the current user, with pagination metadata.

    Reviewers (admin) see every post; other users see only the posts they
    created. Returns ``(posts, total)``.
    """
    author_id = None if _can_review(db, user) else user.id

    posts = list_post_records(
        db,
        section=section,
        status=status,
        author_id=author_id,
        offset=offset,
        limit=limit,
    )
    total = count_posts(
        db,
        section=section,
        status=status,
        author_id=author_id,
    )
    return posts, total


def get_post_or_404(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Fetch a post the user is allowed to see, or raise DomainError."""
    post = get_post_by_id(db, post_id)
    if post is None:
        raise DomainError(f"Post with id {post_id} not found")

    if _can_review(db, user) or post.author_id == user.id:
        return post
    if post.status == PostStatus.published:
        return post

    raise DomainError(f"Post with id {post_id} not found")


def update_post(
    db: Session,
    *,
    user: User,
    post_id: uuid.UUID,
    payload: PostUpdate,
) -> Post:
    """Update a post. Only the author (or a reviewer) may edit it."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if post.author_id != user.id and not _can_review(db, user):
        raise DomainError("You can only edit your own posts")
    if post.status == PostStatus.published and not _can_review(db, user):
        raise DomainError("Published posts cannot be edited")

    return update_post_record(db, post, **_dump_post_data(payload))


def delete_post(db: Session, *, user: User, post_id: uuid.UUID) -> None:
    """Delete a post. Only the author (or a reviewer) may delete it."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if post.author_id != user.id and not _can_review(db, user):
        raise DomainError("You can only delete your own posts")

    delete_post_record(db, post)


def submit_for_review(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Submit a draft (or rejected) post for admin review."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if post.author_id != user.id and not _can_review(db, user):
        raise DomainError("You can only submit your own posts")
    if post.status not in (PostStatus.draft, PostStatus.rejected):
        raise DomainError("Only draft or rejected posts can be submitted for review")

    return set_post_status(db, post, PostStatus.pending_review)


def publish_post(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Publish a post that is pending review (reviewers only)."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if not _can_review(db, user):
        raise DomainError("You do not have permission to publish posts")
    if post.status != PostStatus.pending_review:
        raise DomainError("Only posts pending review can be published")

    return set_post_status(db, post, PostStatus.published)


def reject_post(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Reject a post that is pending review (reviewers only)."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if not _can_review(db, user):
        raise DomainError("You do not have permission to reject posts")
    if post.status != PostStatus.pending_review:
        raise DomainError("Only posts pending review can be rejected")

    return set_post_status(db, post, PostStatus.rejected)
