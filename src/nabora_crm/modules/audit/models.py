import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from nabora_crm.db.base import Base


class AuditAction:
    """Audit action constants.

    Stored as plain strings so new actions do not require a migration.
    """

    # Auth
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    TOKEN_REFRESHED = "auth.token_refreshed"
    PASSWORD_CHANGED = "auth.password_changed"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET = "auth.password_reset"

    # Users
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DEACTIVATED = "user.deactivated"
    USER_ACTIVATED = "user.activated"

    # Invitations
    INVITATION_SENT = "invitation.sent"
    INVITATION_RESENT = "invitation.resent"
    INVITATION_ACCEPTED = "invitation.accepted"

    # Roles
    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    ROLE_DELETED = "role.deleted"

    # Posts
    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_DELETED = "post.deleted"
    POST_SUBMITTED = "post.submitted"
    POST_PUBLISHED = "post.published"
    POST_UNPUBLISHED = "post.unpublished"
    POST_CHANGES_REQUESTED = "post.changes_requested"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Who performed the action (nullable — system-initiated actions have no actor)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # What happened
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # The primary resource affected (e.g. user id, post id, role id)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Human-readable description for display in the admin log
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Client IP address (best-effort, may be None in tests)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index(
            "ix_audit_logs_actor_action_created",
            "actor_id",
            "action",
            "created_at",
        ),
    )
