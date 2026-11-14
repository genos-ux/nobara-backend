import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nabora_crm.core.config import settings
from nabora_crm.core.exceptions import EmailSendError
from nabora_crm.core.permissions import INVITATIONS_WRITE
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.invitations.schemas import (
    AcceptInviteRequest,
    InviteUserRequest,
    InviteUserResponse,
    ResendInviteRequest,
    ResendInviteResponse,
)
from nabora_crm.modules.invitations.service import (
    accept_invitation,
    invite_user,
    resend_invitation,
)
from nabora_crm.modules.users.models import User

logger = logging.getLogger("nabora_crm")

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("", response_model=InviteUserResponse, status_code=201)
def create_invitation(
    payload: InviteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(INVITATIONS_WRITE)),
) -> InviteUserResponse:
    """Send an email invitation to a new user.

    Creates a pending user account and emails them a link to set up their password.
    """
    user = invite_user(
        db,
        full_name=payload.full_name,
        email=payload.email,
        role_id=payload.role_id,
        inviter_name=current_user.email,
    )
    return InviteUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_pending=user.is_pending,
    )


@router.post("/resend", response_model=ResendInviteResponse)
def resend_invitation_endpoint(
    payload: ResendInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(INVITATIONS_WRITE)),
) -> ResendInviteResponse:
    """Re-send an invitation email to a pending user, by user ID or email.

    Generates a fresh token, so this also covers expired invitation links.
    """
    user = resend_invitation(
        db,
        user_id=payload.user_id,
        email=str(payload.email) if payload.email is not None else None,
        inviter_name=current_user.email,
    )
    return ResendInviteResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_pending=user.is_pending,
        expires_in_days=settings.INVITATION_TOKEN_EXPIRE_DAYS,
        message=(
            f"Invitation re-sent to {user.email}. "
            f"The link expires in {settings.INVITATION_TOKEN_EXPIRE_DAYS} day(s)."
        ),
    )


@router.post("/accept", response_model=InviteUserResponse)
def accept_invitation_endpoint(
    payload: AcceptInviteRequest,
    db: Session = Depends(get_db),
) -> InviteUserResponse:
    """Set up a password for an invited user.

    No authentication required — the invitation token serves as proof of identity.
    """
    user = accept_invitation(db, token=payload.token, password=payload.password)
    return InviteUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_pending=user.is_pending,
    )
