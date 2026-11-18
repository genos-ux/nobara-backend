import uuid

from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Authenticated user changes their own password."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

    @model_validator(mode="after")
    def _passwords_differ(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class ForgotPasswordRequest(BaseModel):
    """Request a password reset link."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Set a new password using a reset token."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    permissions: list[str]
    is_active: bool
    is_email_pending: bool
