from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from nabora_crm.db.session import get_db
from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.auth.dependencies import get_current_user, oauth2_scheme
from nabora_crm.modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenRequest,
    UserProfile,
)
from nabora_crm.modules.auth.service import (
    authenticate_user,
    change_password,
    create_token_pair,
    refresh_access_token,
    request_password_reset,
    reset_password,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Logout the current user. Client should discard both tokens."""
    log_action(
        db,
        action=AuditAction.LOGOUT,
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="user",
        resource_id=str(current_user.id),
        detail=f"User '{current_user.email}' logged out.",
    )
    return {"message": "Successfully logged out"}


@router.post("/refresh")
def refresh_token(
    request: TokenRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Issue a new access token using a valid refresh token."""
    return refresh_access_token(db, request.refresh_token)


@router.post("/change-password")
def change_password_endpoint(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Change the current authenticated user's password."""
    change_password(
        db,
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return {"message": "Password updated successfully"}


@router.post("/forgot-password")
def forgot_password_endpoint(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Send a password reset link if the email belongs to an active account."""
    request_password_reset(db, str(payload.email))
    return {
        "message": (
            "If an account with that email exists, a password reset link "
            "has been sent."
        )
    }


@router.post("/reset-password")
def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Set a new password using a valid reset token."""
    reset_password(db, token=payload.token, new_password=payload.new_password)
    return {"message": "Password reset successfully"}


@router.get("/me", response_model=UserProfile)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfile:
    """Return the current authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.name,
        permissions=current_user.permissions,
        is_active=current_user.is_active,
        is_email_pending=current_user.is_email_pending,
    )
