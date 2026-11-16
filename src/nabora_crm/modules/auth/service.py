from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import (
    AuthenticationError,
    DomainError,
    InactiveUserError,
    InvalidRefreshTokenError,
)
from nabora_crm.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from nabora_crm.modules.notifications.models import NotificationType
from nabora_crm.modules.notifications.service import (
    ensure_welcome_notification,
    notify_user,
)
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_email


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise a domain exception."""
    user = get_user_by_email(db, email)
    if not user:
        raise AuthenticationError("Incorrect email or password")
    if user.is_pending:
        raise AuthenticationError("Account not set up — please use the invitation link")
    if not verify_password(password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password")
    if not user.is_active:
        raise InactiveUserError("Inactive user account")
    ensure_welcome_notification(db, user)
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

    token_data = {"sub": user.email, "role": user.role.name}
    return {"access_token": create_access_token(token_data)}
