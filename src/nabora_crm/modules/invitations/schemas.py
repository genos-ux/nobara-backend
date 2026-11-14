import uuid

from pydantic import BaseModel, EmailStr, Field, model_validator


class InviteUserRequest(BaseModel):
    """Admin sends this to invite a new user."""

    full_name: str = Field(min_length=1)
    email: EmailStr
    role_id: uuid.UUID


class ResendInviteRequest(BaseModel):
    """Admin sends this to re-send an invitation, by user ID or email."""

    user_id: uuid.UUID | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> "ResendInviteRequest":
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Provide exactly one of 'user_id' or 'email'")
        return self


class AcceptInviteRequest(BaseModel):
    """Invited user sends this to set their password."""

    token: str
    password: str = Field(min_length=8)


class InviteUserResponse(BaseModel):
    """Returned after a successful invitation."""

    id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    is_pending: bool

    model_config = {"from_attributes": True}


class ResendInviteResponse(InviteUserResponse):
    """Returned after an invitation has been re-sent."""

    expires_in_days: int
    message: str
