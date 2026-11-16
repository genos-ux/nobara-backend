import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from nabora_crm.modules.notifications.models import Notification
from nabora_crm.modules.roles.models import Permission, Role, role_permissions
from nabora_crm.modules.users.models import User


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    message: str,
    post_id: uuid.UUID | None = None,
) -> Notification:
    """Add a single notification and commit it."""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        post_id=post_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def create_notifications(
    db: Session,
    *,
    user_ids: list[uuid.UUID],
    notification_type: str,
    title: str,
    message: str,
    post_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Add one notification per user and commit them in a single transaction."""
    notifications = [
        Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            post_id=post_id,
        )
        for user_id in dict.fromkeys(user_ids)
    ]
    if not notifications:
        return []
    db.add_all(notifications)
    db.commit()
    for notification in notifications:
        db.refresh(notification)
    return notifications


def list_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    unread_only: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> list[Notification]:
    """Return a user's notifications, newest first."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = (
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def count_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    unread_only: bool = False,
) -> int:
    """Count a user's notifications."""
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.execute(stmt).scalar_one()


def count_unread(db: Session, *, user_id: uuid.UUID) -> int:
    """Count a user's unread notifications."""
    return count_notifications(db, user_id=user_id, unread_only=True)


def get_notification(
    db: Session,
    *,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification | None:
    """Fetch one of a user's notifications by ID."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def mark_notification_read(db: Session, notification: Notification) -> Notification:
    """Mark a notification as read and commit."""
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, *, user_id: uuid.UUID) -> int:
    """Mark all of a user's unread notifications as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=func.now())
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def list_notifications_after(
    db: Session,
    *,
    user_id: uuid.UUID,
    after: datetime,
    limit: int = 100,
) -> list[Notification]:
    """Return notifications newer than ``after``, oldest first."""
    stmt = (
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.created_at > after,
        )
        .order_by(Notification.created_at.asc(), Notification.id.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_active_user_ids_with_permission(
    db: Session,
    permission: str,
) -> list[uuid.UUID]:
    """Return active users whose role grants ``permission``."""
    stmt = (
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .join(
            role_permissions,
            role_permissions.c.role_id == Role.id,
        )
        .join(
            Permission,
            Permission.id == role_permissions.c.permission_id,
        )
        .where(
            Permission.name == permission,
            User.is_active.is_(True),
        )
        .distinct()
    )
    return list(db.execute(stmt).scalars().all())


def list_active_user_ids_by_role(
    db: Session,
    role_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Return active users assigned to ``role_id``."""
    stmt = select(User.id).where(
        User.role_id == role_id,
        User.is_active.is_(True),
    )
    return list(db.execute(stmt).scalars().all())
