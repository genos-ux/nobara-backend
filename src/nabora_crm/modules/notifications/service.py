import logging
import uuid

from sqlalchemy.orm import Session

from nabora_crm.modules.notifications.broker import notification_broker
from nabora_crm.modules.notifications.models import Notification, NotificationType
from nabora_crm.modules.notifications.repository import (
    count_notifications,
    create_notifications,
    list_active_user_ids_by_role,
    list_active_user_ids_with_permission,
)
from nabora_crm.modules.notifications.schemas import NotificationOut
from nabora_crm.modules.users.models import User

logger = logging.getLogger("nabora_crm")


def notification_payload(notification: Notification) -> dict:
    """Serialize a notification for SSE delivery."""
    return NotificationOut.model_validate(notification).model_dump(mode="json")


def notify_users(
    db: Session,
    user_ids: list[uuid.UUID],
    *,
    notification_type: str,
    title: str,
    message: str,
    post_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Create notifications for several users and publish them live.

    Notifications are best-effort: a failure must not break the action that
    triggered them. Callers should invoke this after their main transaction has
    committed.
    """
    if not user_ids:
        return []
    try:
        notifications = create_notifications(
            db,
            user_ids=user_ids,
            notification_type=notification_type,
            title=title,
            message=message,
            post_id=post_id,
        )
        for notification in notifications:
            notification_broker.publish(
                notification.user_id, notification_payload(notification)
            )
        return notifications
    except Exception:
        logger.exception("Failed to create notifications")
        db.rollback()
        return []


def notify_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    notification_type: str,
    title: str,
    message: str,
    post_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Create a notification for one user."""
    return notify_users(
        db,
        [user_id],
        notification_type=notification_type,
        title=title,
        message=message,
        post_id=post_id,
    )


def notify_permission(
    db: Session,
    permission: str,
    *,
    notification_type: str,
    title: str,
    message: str,
    post_id: uuid.UUID | None = None,
    exclude_user_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Notify every active user whose role grants ``permission``."""
    try:
        user_ids = list_active_user_ids_with_permission(db, permission)
    except Exception:
        logger.exception("Failed to resolve notification recipients")
        db.rollback()
        return []
    if exclude_user_id is not None:
        user_ids = [user_id for user_id in user_ids if user_id != exclude_user_id]
    return notify_users(
        db,
        user_ids,
        notification_type=notification_type,
        title=title,
        message=message,
        post_id=post_id,
    )


def notify_role_members(
    db: Session,
    role_id: uuid.UUID,
    role_name: str,
) -> list[Notification]:
    """Notify every active user assigned to a role that the role changed."""
    try:
        user_ids = list_active_user_ids_by_role(db, role_id)
    except Exception:
        logger.exception("Failed to resolve role members for notification")
        db.rollback()
        return []
    return notify_users(
        db,
        user_ids,
        notification_type=NotificationType.ROLE_UPDATED,
        title="Role updated",
        message=f"Your role '{role_name}' was updated by an administrator.",
    )


def ensure_welcome_notification(db: Session, user: User) -> list[Notification]:
    """Create a one-time welcome notification for a user with no history."""
    try:
        existing = count_notifications(db, user_id=user.id)
    except Exception:
        logger.exception("Failed to check welcome notification state")
        db.rollback()
        return []
    if existing:
        return []
    name = user.full_name or user.email
    return notify_user(
        db,
        user.id,
        notification_type=NotificationType.WELCOME,
        title="Welcome to Nabora",
        message=f"Welcome, {name}. You're all set up and ready to go.",
    )
