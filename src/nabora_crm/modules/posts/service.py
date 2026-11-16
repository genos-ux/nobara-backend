import uuid

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.core.permissions import POSTS_REVIEW
from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import (
    notify_permission,
    notify_user,
)
from nabora_crm.modules.posts.models import Post, PostSection, PostStatus, PostTopic
from nabora_crm.modules.posts.repository import (
    count_posts,
    count_posts_by_status,
    create_post as create_post_record,
    delete_post as delete_post_record,
    get_post_by_id,
    list_posts as list_post_records,
    set_post_changes_requested,
    set_post_status,
    update_post as update_post_record,
)
from nabora_crm.modules.posts.schemas import PostCreate, PostUpdate
from nabora_crm.modules.roles.repository import get_user_permissions
from nabora_crm.modules.users.models import User


def _has_permission(db: Session, user: User, permission: str) -> bool:
    return permission in set(get_user_permissions(db, user.role_id))


def can_review(db: Session, user: User) -> bool:
    """Return True when the user's role grants ``posts:review``.

    Visibility is driven by permissions, not role names, so renaming a role
    does not change who can see every post.
    """
    return _has_permission(db, user, POSTS_REVIEW)


def _post_label(post: Post) -> str:
    return post.headline or "Untitled post"


def _user_label(user: User) -> str:
    return user.full_name or user.email


def _notify_reviewers_of_submission(db: Session, *, post: Post, actor: User) -> None:
    notify_permission(
        db,
        POSTS_REVIEW,
        notification_type=NotificationType.POST_SUBMITTED,
        title="New post submitted for review",
        message=f'{_user_label(actor)} submitted "{_post_label(post)}" for review.',
        post_id=post.id,
        exclude_user_id=actor.id,
    )


def _dump_post_data(payload: PostCreate | PostUpdate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if data.get("image_url") is not None:
        data["image_url"] = str(data["image_url"])
    return data


def create_post(db: Session, *, user: User, payload: PostCreate) -> Post:
    """Create a new post authored by the current user."""
    post = create_post_record(
        db,
        author_id=user.id,
        **_dump_post_data(payload),
    )
    log_action(
        db,
        action=AuditAction.POST_CREATED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Post '{_post_label(post)}' created with status '{post.status.value}'.",
    )
    if post.status == PostStatus.pending_review:
        _notify_reviewers_of_submission(db, post=post, actor=user)
    return post


def list_posts(
    db: Session,
    *,
    user: User,
    section: PostSection | None = None,
    topic: PostTopic | None = None,
    status: PostStatus | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[Post], int]:
    """List posts visible to the current user, with pagination metadata.

    Users whose role grants ``posts:review`` see every post (the admin
    overview of contributor work); everyone else sees only their own posts.
    Visibility is permission-based, not role-name-based. Returns
    ``(posts, total)``.
    """
    author_id = None if can_review(db, user) else user.id

    posts = list_post_records(
        db,
        section=section,
        topic=topic,
        status=status,
        author_id=author_id,
        offset=offset,
        limit=limit,
    )
    total = count_posts(
        db,
        section=section,
        topic=topic,
        status=status,
        author_id=author_id,
    )
    return posts, total


def get_post_or_404(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Fetch a post the user is allowed to see, or raise DomainError."""
    post = get_post_by_id(db, post_id)
    if post is None:
        raise DomainError(f"Post with id {post_id} not found")

    if can_review(db, user) or post.author_id == user.id:
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

    if post.author_id != user.id and not can_review(db, user):
        raise DomainError("You can only edit your own posts")
    if post.status == PostStatus.published and not can_review(db, user):
        raise DomainError("Published posts cannot be edited")

    is_author = post.author_id == user.id
    post = update_post_record(db, post, **_dump_post_data(payload))
    log_action(
        db,
        action=AuditAction.POST_UPDATED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Post '{_post_label(post)}' updated by '{_user_label(user)}'.",
    )
    if not is_author:
        notify_user(
            db,
            post.author_id,
            notification_type=NotificationType.POST_UPDATED,
            title="Post updated",
            message=(
                f'Your post "{_post_label(post)}" was updated by '
                f"{_user_label(user)}."
            ),
            post_id=post.id,
        )
    return post


def delete_post(db: Session, *, user: User, post_id: uuid.UUID) -> None:
    """Delete a post. Only the author (or a reviewer) may delete it."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if post.author_id != user.id and not can_review(db, user):
        raise DomainError("You can only delete your own posts")

    author_id = post.author_id
    label = _post_label(post)
    post_id_str = str(post.id)
    is_author = author_id == user.id
    delete_post_record(db, post)

    log_action(
        db,
        action=AuditAction.POST_DELETED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=post_id_str,
        detail=f"Post '{label}' deleted by '{_user_label(user)}'.",
    )
    if not is_author:
        notify_user(
            db,
            author_id,
            notification_type=NotificationType.POST_DELETED,
            title="Post deleted",
            message=(
                f'Your post "{label}" was deleted by {_user_label(user)}.'
            ),
        )


def submit_for_review(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Submit a draft (or unpublished) post for admin review."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if post.author_id != user.id and not can_review(db, user):
        raise DomainError("You can only submit your own posts")
    if post.status not in (
        PostStatus.draft,
        PostStatus.unpublished,
        PostStatus.changes_requested,
    ):
        raise DomainError(
            "Only draft, unpublished, or changes-requested posts can be "
            "submitted for review"
        )

    if post.status == PostStatus.changes_requested:
        post.review_note = None

    post = set_post_status(db, post, PostStatus.pending_review)
    log_action(
        db,
        action=AuditAction.POST_SUBMITTED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Post '{_post_label(post)}' submitted for review by '{_user_label(user)}'.",
    )
    _notify_reviewers_of_submission(db, post=post, actor=user)
    return post


def request_changes(
    db: Session,
    *,
    user: User,
    post_id: uuid.UUID,
    note: str,
) -> Post:
    """Request changes on a post pending review (reviewers only)."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if not can_review(db, user):
        raise DomainError("You do not have permission to request changes")
    if post.status != PostStatus.pending_review:
        raise DomainError("Changes can only be requested on posts pending review")

    post = set_post_changes_requested(db, post, note)
    log_action(
        db,
        action=AuditAction.POST_CHANGES_REQUESTED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Changes requested on '{_post_label(post)}' by '{_user_label(user)}': {note}",
    )
    if post.author_id != user.id:
        notify_user(
            db,
            post.author_id,
            notification_type=NotificationType.POST_CHANGES_REQUESTED,
            title="Changes requested",
            message=(
                f'Changes were requested on "{_post_label(post)}": {note}'
            ),
            post_id=post.id,
        )
    return post


def publish_post(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Publish a post that is pending review (reviewers only)."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if not can_review(db, user):
        raise DomainError("You do not have permission to publish posts")
    if post.status != PostStatus.pending_review:
        raise DomainError("Only posts pending review can be published")

    post = set_post_status(db, post, PostStatus.published)
    log_action(
        db,
        action=AuditAction.POST_PUBLISHED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Post '{_post_label(post)}' published by '{_user_label(user)}'.",
    )
    if post.author_id != user.id:
        notify_user(
            db,
            post.author_id,
            notification_type=NotificationType.POST_PUBLISHED,
            title="Post published",
            message=f'Your post "{_post_label(post)}" has been published.',
            post_id=post.id,
        )
    return post


def unpublish_post(db: Session, *, user: User, post_id: uuid.UUID) -> Post:
    """Unpublish a published post (reviewers only)."""
    post = get_post_or_404(db, user=user, post_id=post_id)

    if not can_review(db, user):
        raise DomainError("You do not have permission to unpublish posts")
    if post.status != PostStatus.published:
        raise DomainError("Only published posts can be unpublished")

    post = set_post_status(db, post, PostStatus.unpublished)
    log_action(
        db,
        action=AuditAction.POST_UNPUBLISHED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="post",
        resource_id=str(post.id),
        detail=f"Post '{_post_label(post)}' unpublished by '{_user_label(user)}'.",
    )
    if post.author_id != user.id:
        notify_user(
            db,
            post.author_id,
            notification_type=NotificationType.POST_UNPUBLISHED,
            title="Post unpublished",
            message=f'Your post "{_post_label(post)}" has been unpublished.',
            post_id=post.id,
        )
    return post


def get_post_status_counts(db: Session, *, user: User) -> dict[PostStatus, int]:
    """Return post counts per status visible to the current user."""
    author_id = None if can_review(db, user) else user.id
    return count_posts_by_status(db, author_id=author_id)
