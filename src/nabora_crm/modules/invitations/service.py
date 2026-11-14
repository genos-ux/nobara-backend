import logging
import uuid

from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.email import send_invitation_email
from nabora_crm.core.exceptions import DomainError, EmailSendError, InvalidTokenError
from nabora_crm.core.security import (
    create_invitation_token,
    decode_invitation_token,
    hash_password,
)
from nabora_crm.modules.invitations.repository import (
    create_pending_user,
    get_user_by_email,
    get_user_by_id,
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
) -> User:
    """Create a pending user and send an invitation email.

    Raises:
        DomainError: If the email is already in use by an active user.
        EmailSendError: If the email could not be sent.
    """
    # An email may only ever be invited once. Pending users should use the
    # resend endpoint; active users cannot be invited again.
    existing = get_user_by_email(db, email)
    if existing is not None:
        raise DomainError(f"A user with email '{email}' already exists in the system")

    # Validate role exists
    role = get_role_by_id(db, role_id)
    if role is None:
        raise DomainError(f"Role with id {role_id} not found")

    user = create_pending_user(
        db, full_name=full_name, email=email, role_id=role_id
    )

    # Generate invitation token
    token = create_invitation_token({"sub": str(user.id), "email": user.email})

    # Send the invitation email
    send_invitation_email(
        to_email=user.email,
        invite_token=token,
        inviter_name=inviter_name,
    )

    logger.info("Invitation sent to %s", email)
    return user


def resend_invitation(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    inviter_name: str | None = None,
) -> User:
    """Generate a fresh token and re-send an invitation email.

    Identifies the user by ID or email. Only pending users (who have not yet
    set their password) can be re-invited.

    Raises:
        DomainError: If no identifier is given, the user is not found, or the
                     user has already completed the invitation.
        EmailSendError: If the email could not be sent.
    """
    if user_id is not None:
        user = get_user_by_id(db, user_id)
    elif email is not None:
        user = get_user_by_email(db, email)
    else:
        raise DomainError("Provide either a user id or an email to resend an invitation")

    if user is None:
        identifier = user_id if user_id is not None else email
        raise DomainError(f"No user found for {identifier}")

    if not user.is_pending:
        raise DomainError(
            f"User '{user.email}' has already completed setup; no invitation to resend"
        )

    token = create_invitation_token({"sub": str(user.id), "email": user.email})
    send_invitation_email(
        to_email=user.email,
        invite_token=token,
        inviter_name=inviter_name,
    )

    logger.info("Invitation re-sent to %s", user.email)
    return user


def accept_invitation(db: Session, *, token: str, password: str) -> User:
    """Validate an invitation token and set the user's password.

    Raises:
        InvalidTokenError: If the token is missing, malformed, expired,
                           or does not match a pending user.
    """
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

    if not user.is_pending:
        raise InvalidTokenError("This invitation has already been used")

    # Set password and activate the user
    user.hashed_password = hash_password(password)
    user.is_pending = False
    db.commit()
    db.refresh(user)

    logger.info("User %s completed invitation setup", user.email)
    return user
