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
    get_pending_user_by_email,
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
    # Check for existing non-pending user with this email
    existing = get_user_by_email(db, email)
    if existing and not existing.is_pending:
        raise DomainError(f"A user with email '{email}' already exists")

    # Validate role exists
    role = get_role_by_id(db, role_id)
    if role is None:
        raise DomainError(f"Role with id {role_id} not found")

    # Reuse existing pending user or create a new one
    pending = get_pending_user_by_email(db, email)
    if pending:
        user = pending
        # Update details if re-invited with different values
        changed = False
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if str(user.role_id) != str(role_id):
            user.role_id = role_id
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
    else:
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
