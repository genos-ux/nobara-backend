from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import (
    AdminPrivilegeRequiredError,
    InactiveUserError,
    InvalidTokenError,
)
from nabora_crm.core.security import decode_access_token
from nabora_crm.db.session import get_db
from nabora_crm.modules.users.models import Role, User
from nabora_crm.modules.users.repository import get_user_by_email

oauth2_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT token and return the current authenticated user."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if email is None or token_type != "access":
            raise InvalidTokenError("Could not validate credentials")
    except JWTError:
        raise InvalidTokenError("Could not validate credentials")

    user = get_user_by_email(db, email)
    if user is None:
        raise InvalidTokenError("Could not validate credentials")
    if not user.is_active:
        raise InactiveUserError("Inactive user account")
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user has the admin role."""
    if current_user.role != Role.admin:
        raise AdminPrivilegeRequiredError("Admin privileges required")
    return current_user
