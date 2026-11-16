import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from nabora_crm.db.base import Base


class NotificationType:
    """Notification type constants.

    Stored as plain strings so new event types do not require a migration.
    """

    WELCOME = "welcome"
    ACCOUNT_CREATED = "account_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    USER_ACTIVATED = "user_activated"
    PASSWORD_CHANGED = "password_changed"
    ROLE_CHANGED = "role_changed"
    ROLE_UPDATED = "role_updated"
    INVITATION_ACCEPTED = "invitation_accepted"
    POST_SUBMITTED = "post_submitted"
    POST_PUBLISHED = "post_published"
    POST_UNPUBLISHED = "post_unpublished"
    POST_CHANGES_REQUESTED = "post_changes_requested"
    POST_UPDATED = "post_updated"
    POST_DELETED = "post_deleted"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_notifications_user_read_created",
            "user_id",
            "is_read",
            "created_at",
        ),
    )
