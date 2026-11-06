from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import get_current_user, oauth2_scheme
from nabora_crm.modules.auth.schemas import LoginRequest, TokenRequest, UserProfile
from nabora_crm.modules.auth.service import (
    authenticate_user,
    create_token_pair,
    refresh_access_token,
)
from nabora_crm.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Authenticate a user and return access and refresh tokens."""
    user = authenticate_user(db, credentials.email, credentials.password)
    return create_token_pair(user)


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> dict[str, str]:
    """Logout the current user. Client should discard both tokens."""
    return {
        "message": "Successfully logged out",
    }


@router.post("/refresh")
def refresh_token(
    request: TokenRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Issue a new access token using a valid refresh token."""
    return refresh_access_token(db, request.refresh_token)


@router.get("/me", response_model=UserProfile)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfile:
    """Return the current authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
