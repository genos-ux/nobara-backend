import logging
import uuid

from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.email import send_invitation_email
from nabora_crm.core.exceptions import DomainError, EmailSendError, InvalidTokenError
from nabora_crm.core.permissions import INVITATIONS_WRITE
from nabora_crm.core.security import (
    create_invitation_token,
    decode_invitation_token,
    hash_password,
)
from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.invitations.repository import (
    create_pending_user,
    get_user_by_email,
    get_user_by_id,
)
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import (
    ensure_welcome_notification,
    notify_permission,
)
from nabora_crm.modules.roles.repository import get_role_by_id
from nabora_crm.modules.users.models import User

logger = logging.getLogger("nabora_crm")


def invite_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    role_id: str,
    inviter_name: str | None = None,
    actor: User | None = None,
) -> User:
    """Create a pending user and send an invitation email."""
    existing = get_user_by_email(db, email)
    if existing is not None:
        raise DomainError(f"A user with email '{email}' already exists in the system")

    role = get_role_by_id(db, role_id)
    if role is None:
        raise DomainError(f"Role with id {role_id} not found")

    user = create_pending_user(
        db, full_name=full_name, email=email, role_id=role_id
    )

    token = create_invitation_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "ver": user.invitation_token_version,
        }
    )

    send_invitation_email(
        to_email=user.email,
        invite_token=token,
        inviter_name=inviter_name,
    )

    log_action(
        db,
        action=AuditAction.INVITATION_SENT,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"Invitation sent to '{email}' with role '{role.name}'.",
    )
    logger.info("Invitation sent to %s", email)
    return user


def resend_invitation(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    inviter_name: str | None = None,
    actor: User | None = None,
) -> User:
    """Generate a fresh token and re-send an invitation email."""
    if user_id is not None:
        user = get_user_by_id(db, user_id)
    elif email is not None:
        user = get_user_by_email(db, email)
    else:
        raise DomainError("Provide either a user id or an email to resend an invitation")

    if user is None:
        identifier = user_id if user_id is not None else email
        raise DomainError(f"No user found for {identifier}")

    if not user.is_email_pending or not user.is_pending:
        raise DomainError(
            f"User '{user.email}' has already set up their password; "
            "no invitation to resend"
        )

    previous_version = user.invitation_token_version
    user.invitation_token_version = previous_version + 1
    db.commit()

    token = create_invitation_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "ver": user.invitation_token_version,
        }
    )
    try:
        send_invitation_email(
            to_email=user.email,
            invite_token=token,
            inviter_name=inviter_name,
        )
    except EmailSendError:
        user.invitation_token_version = previous_version
        db.commit()
        raise

    log_action(
        db,
        action=AuditAction.INVITATION_RESENT,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"Invitation re-sent to '{user.email}'.",
    )
    logger.info("Invitation re-sent to %s", user.email)
    return user


def accept_invitation(db: Session, *, token: str, password: str) -> User:
    """Validate an invitation token and set the user's password."""
    try:
        payload = decode_invitation_token(token)
        token_type: str | None = payload.get("type")
        user_id: str | None = payload.get("sub")
        if token_type != "invitation" or user_id is None:
            raise InvalidTokenError("Invalid invitation token")
    except JWTError:
        raise InvalidTokenError("Invalid or expired invitation token")

    user = get_user_by_id(db, uuid.UUID(user_id))
    if user is None:
        raise InvalidTokenError("Invalid invitation token")

    if payload.get("ver", 0) != user.invitation_token_version:
        raise InvalidTokenError(
            "This invitation link is no longer valid. Ask for a new invitation."
        )

    if not user.is_pending:
        raise InvalidTokenError("This invitation has already been used")

    user.hashed_password = hash_password(password)
    user.is_pending = False
    user.is_email_pending = False
    db.commit()
    db.refresh(user)

    name = user.full_name or user.email
    notify_permission(
        db,
        INVITATIONS_WRITE,
        notification_type=NotificationType.INVITATION_ACCEPTED,
        title="New user joined",
        message=f"{name} accepted their invitation and joined the system.",
        exclude_user_id=user.id,
    )
    ensure_welcome_notification(db, user)
    log_action(
        db,
        action=AuditAction.INVITATION_ACCEPTED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"'{user.email}' accepted their invitation and set up their account.",
    )

    logger.info("User %s completed invitation setup", user.email)
    return user
