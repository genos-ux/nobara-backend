import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
)
from nabora_crm.core.security import decode_access_token, decode_stream_ticket
from nabora_crm.db.session import get_db
from nabora_crm.modules.roles.repository import get_user_permissions
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_email, get_user_by_id

oauth2_scheme = HTTPBearer()
optional_oauth2_scheme = HTTPBearer(auto_error=False)


def resolve_access_token(db: Session, token: str) -> User:
    """Resolve an access token to an active user."""
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


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT token and return the current authenticated user."""
    return resolve_access_token(db, credentials.credentials)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the current user when a valid token is supplied, else ``None``.

    Used by endpoints that are publicly readable but can show more data to
    authenticated users. A supplied-but-invalid token is still rejected.
    """
    if credentials is None:
        return None
    return resolve_access_token(db, credentials.credentials)


def resolve_stream_ticket(db: Session, ticket: str) -> User:
    """Resolve a short-lived SSE ticket to an active user."""
    try:
        payload = decode_stream_ticket(ticket)
        subject: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if subject is None or token_type != "sse":
            raise InvalidTokenError("Could not validate stream ticket")
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError):
        raise InvalidTokenError("Could not validate stream ticket")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise InvalidTokenError("Could not validate stream ticket")
    if not user.is_active:
        raise InactiveUserError("Inactive user account")
    return user


def require_permission(permission: str) -> Callable:
    """Return a FastAPI dependency that checks the user has the given permission.

    Usage in a router:

        @router.get("/users", dependencies=[Depends(require_permission("users:read"))])
        def list_users(...): ...

    or as a parameter dependency to get the user object:

        def list_users(_user=Depends(require_permission("users:read"))): ...
    """

    def _check(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Session = Depends(get_db),
    ) -> User:
        user_perms = set(get_user_permissions(db, current_user.role_id))
        if permission not in user_perms:
            raise PermissionDeniedError(
                f"Permission '{permission}' is required to perform this action"
            )
        return current_user

    return _check
