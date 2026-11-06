from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from nabora_crm.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_email


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise HTTPException."""
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


def create_token_pair(user: User) -> dict[str, str]:
    """Create access and refresh tokens for a user."""
    token_data = {"sub": user.email, "role": user.role.value}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, str]:
    """Validate a refresh token and return a new access token."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = decode_refresh_token(refresh_token)
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise credentials_exc

    token_data = {"sub": user.email, "role": user.role.value}
    return {"access_token": create_access_token(token_data)}
