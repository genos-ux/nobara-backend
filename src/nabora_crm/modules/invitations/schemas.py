import uuid

from pydantic import BaseModel, EmailStr, Field


class InviteUserRequest(BaseModel):
    """Admin sends this to invite a new user."""

    email: EmailStr
    role_id: uuid.UUID


class AcceptInviteRequest(BaseModel):
    """Invited user sends this to set their password."""

    token: str
    password: str = Field(min_length=8)


class InviteUserResponse(BaseModel):
    """Returned after a successful invitation."""

    id: uuid.UUID
    email: str
    role: str
    is_pending: bool

    model_config = {"from_attributes": True}
