import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import DomainError
from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import notify_user
from nabora_crm.modules.posts.models import Post
from nabora_crm.modules.roles.repository import get_role_by_id
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import (
    get_posts_by_author_ids,
    get_user_by_email,
    get_user_by_id,
    list_users as list_user_records,
)


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    """Fetch a user by ID or raise DomainError."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise DomainError(f"User with id {user_id} not found")
    return user


def set_user_active(
    db: Session,
    user: User,
    is_active: bool,
    *,
    actor: User | None = None,
) -> User:
    """Activate or deactivate a user and commit."""
    was_active = user.is_active
    user.is_active = is_active
    db.commit()
    db.refresh(user)

    if was_active != is_active:
        if is_active:
            notify_user(
                db,
                user.id,
                notification_type=NotificationType.USER_ACTIVATED,
                title="Account reactivated",
                message="Your account has been reactivated.",
            )
            log_action(
                db,
                action=AuditAction.USER_ACTIVATED,
                actor_id=actor.id if actor else None,
                actor_email=actor.email if actor else None,
                resource_type="user",
                resource_id=str(user.id),
                detail=f"User '{user.email}' was activated.",
            )
        else:
            notify_user(
                db,
                user.id,
                notification_type=NotificationType.USER_DEACTIVATED,
                title="Account deactivated",
                message="Your account has been deactivated.",
            )
            log_action(
                db,
                action=AuditAction.USER_DEACTIVATED,
                actor_id=actor.id if actor else None,
                actor_email=actor.email if actor else None,
                resource_type="user",
                resource_id=str(user.id),
                detail=f"User '{user.email}' was deactivated.",
            )
    return user


def update_user_details(
    db: Session,
    user: User,
    *,
    full_name: str | None = None,
    email: str | None = None,
    role_id: uuid.UUID | None = None,
    actor: User | None = None,
) -> User:
    """Update a user's personal details and role, then commit.

    Raises:
        DomainError: If the new email is already used by another user, or the
                     role does not exist.
    """
    previous_role_id = user.role_id
    previous_full_name = user.full_name
    previous_email = user.email

    if email is not None and email != user.email:
        existing = get_user_by_email(db, email)
        if existing is not None and existing.id != user.id:
            raise DomainError(
                f"A user with email '{email}' already exists in the system"
            )
        user.email = email

    if full_name is not None:
        user.full_name = full_name

    if role_id is not None:
        role = get_role_by_id(db, role_id)
        if role is None:
            raise DomainError(f"Role with id {role_id} not found")
        user.role_id = role_id

    db.commit()
    db.refresh(user)

    if user.role_id != previous_role_id:
        notify_user(
            db,
            user.id,
            notification_type=NotificationType.ROLE_CHANGED,
            title="Role changed",
            message=f"Your role was changed to '{user.role.name}'.",
        )

    if (
        user.full_name != previous_full_name
        or user.email != previous_email
        or user.role_id != previous_role_id
    ):
        changes: list[str] = []
        if user.full_name != previous_full_name:
            changes.append(f"name → '{user.full_name}'")
        if user.email != previous_email:
            changes.append(f"email → '{user.email}'")
        if user.role_id != previous_role_id:
            changes.append(f"role → '{user.role.name}'")

        notify_user(
            db,
            user.id,
            notification_type=NotificationType.USER_UPDATED,
            title="Account updated",
            message="Your account details were updated by an administrator.",
        )
        log_action(
            db,
            action=AuditAction.USER_UPDATED,
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            resource_type="user",
            resource_id=str(user.id),
            detail=f"User '{user.email}' updated: {', '.join(changes)}.",
        )

    return user


def list_users(
    db: Session,
    *,
    search: str | None = None,
    role_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[tuple[User, list[Post]]], int]:
    """Return users paired with their posts, plus the total count.

    Names and emails are encrypted, so substring search and name/email sorting
    happen in Python on the decrypted values. This is fine for a staff-sized
    user table but does not scale to very large user counts.
    """
    users = list_user_records(db, role_id=role_id)

    if search and search.strip():
        needle = search.strip().casefold()
        users = [
            user
            for user in users
            if needle in (user.full_name or "").casefold()
            or needle in user.email.casefold()
        ]

    users.sort(key=lambda user: ((user.full_name or "").casefold(), user.email.casefold()))

    total = len(users)
    if offset:
        users = users[offset:]
    if limit is not None:
        users = users[:limit]

    posts_by_author: dict[uuid.UUID, list[Post]] = defaultdict(list)
    for post in get_posts_by_author_ids(db, [u.id for u in users]):
        posts_by_author[post.author_id].append(post)
    results = [(u, posts_by_author[u.id]) for u in users]
    return results, total
