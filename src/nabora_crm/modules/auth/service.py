import logging
import uuid

from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.email import send_password_reset_email
from nabora_crm.core.exceptions import (
    AuthenticationError,
    DomainError,
    EmailSendError,
    InactiveUserError,
    InvalidRefreshTokenError,
    InvalidTokenError,
)
from nabora_crm.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import (
    ensure_welcome_notification,
    notify_user,
)
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_email, get_user_by_id

logger = logging.getLogger("nabora_crm")


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise a domain exception."""
    user = get_user_by_email(db, email)
    if not user:
        log_action(
            db,
            action=AuditAction.LOGIN,
            actor_email=email,
            detail=f"Failed login attempt for unknown email '{email}'.",
        )
        raise AuthenticationError("Incorrect email or password")
    if user.is_pending:
        log_action(
            db,
            action=AuditAction.LOGIN,
            actor_id=user.id,
            actor_email=user.email,
            resource_type="user",
            resource_id=str(user.id),
            detail=f"Failed login attempt for '{email}' — account not set up yet.",
        )
        raise AuthenticationError("Account not set up — please use the invitation link")
    if not verify_password(password, user.hashed_password):
        log_action(
            db,
            action=AuditAction.LOGIN,
            actor_id=user.id,
            actor_email=user.email,
            resource_type="user",
            resource_id=str(user.id),
            detail=f"Failed login attempt for '{email}' — wrong password.",
        )
        raise AuthenticationError("Incorrect email or password")
    if not user.is_active:
        log_action(
            db,
            action=AuditAction.LOGIN,
            actor_id=user.id,
            actor_email=user.email,
            resource_type="user",
            resource_id=str(user.id),
            detail=f"Failed login attempt for '{email}' — account inactive.",
        )
        raise InactiveUserError("Inactive user account")
    ensure_welcome_notification(db, user)
    log_action(
        db,
        action=AuditAction.LOGIN,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"User '{user.email}' logged in.",
    )
    return user


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
) -> User:
    """Change a user's password after verifying the current one.

    Raises:
        DomainError: If the current password is incorrect or the new password
                     matches the current one.
    """
    if not verify_password(current_password, user.hashed_password):
        raise DomainError("Current password is incorrect")

    if verify_password(new_password, user.hashed_password):
        raise DomainError("New password must be different from the current password")

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    notify_user(
        db,
        user.id,
        notification_type=NotificationType.PASSWORD_CHANGED,
        title="Password changed",
        message="Your password was changed successfully.",
    )
    log_action(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"User '{user.email}' changed their password.",
    )
    return user


def request_password_reset(db: Session, email: str) -> None:
    """Send a password reset link when the email belongs to an active user.

    The caller must return the same response whether or not the account exists
    so this endpoint cannot be used to enumerate users. Pending and inactive
    accounts are intentionally ignored.
    """
    user = get_user_by_email(db, email)
    if user is None or user.is_pending or not user.is_active:
        return

    previous_version = user.password_reset_token_version
    user.password_reset_token_version = previous_version + 1
    db.commit()

    token = create_password_reset_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "ver": user.password_reset_token_version,
        }
    )

    try:
        send_password_reset_email(
            to_email=user.email,
            reset_token=token,
            to_name=user.full_name,
        )
    except EmailSendError:
        user.password_reset_token_version = previous_version
        db.commit()
        logger.exception("Failed to send password reset email to %s", user.email)
        return

    log_action(
        db,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"Password reset requested for '{user.email}'.",
    )
    logger.info("Password reset email sent to %s", user.email)


def reset_password(db: Session, *, token: str, new_password: str) -> User:
    """Validate a password reset token and set a new password.

    The token is single-use: the stored token version is incremented after a
    successful reset, invalidating the link and any older reset links.
    """
    try:
        payload = decode_password_reset_token(token)
        token_type: str | None = payload.get("type")
        user_id: str | None = payload.get("sub")
        if token_type != "password_reset" or user_id is None:
            raise InvalidTokenError("Invalid password reset token")
    except JWTError:
        raise InvalidTokenError("Invalid or expired password reset token")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise InvalidTokenError("Invalid password reset token")

    user = get_user_by_id(db, user_uuid)
    if user is None or not user.is_active or user.is_pending:
        raise InvalidTokenError("Invalid password reset token")

    if payload.get("ver", 0) != user.password_reset_token_version:
        raise InvalidTokenError(
            "This password reset link is no longer valid. Request a new one."
        )

    if verify_password(new_password, user.hashed_password):
        raise DomainError("New password must be different from the current password")

    user.hashed_password = hash_password(new_password)
    user.password_reset_token_version += 1
    db.commit()
    db.refresh(user)

    notify_user(
        db,
        user.id,
        notification_type=NotificationType.PASSWORD_CHANGED,
        title="Password reset",
        message="Your password was reset successfully.",
    )
    log_action(
        db,
        action=AuditAction.PASSWORD_RESET,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"User '{user.email}' reset their password.",
    )
    logger.info("Password reset completed for %s", user.email)
    return user


def create_token_pair(user: User) -> dict[str, str]:
    """Create access and refresh tokens for a user."""
    token_data = {"sub": user.email, "role": user.role.name}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, str]:
    """Validate a refresh token and return a new access token."""
    try:
        payload = decode_refresh_token(refresh_token)
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if email is None or token_type != "refresh":
            raise InvalidRefreshTokenError("Invalid or expired refresh token")
    except JWTError:
        raise InvalidRefreshTokenError("Invalid or expired refresh token")

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError("Invalid or expired refresh token")

    log_action(
        db,
        action=AuditAction.TOKEN_REFRESHED,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"User '{user.email}' refreshed their access token.",
    )

    token_data = {"sub": user.email, "role": user.role.name}
    return {"access_token": create_access_token(token_data)}
