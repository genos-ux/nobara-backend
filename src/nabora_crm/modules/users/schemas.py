import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from nabora_crm.modules.posts.models import PostSection, PostStatus


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    is_active: bool
    is_email_pending: bool


class UserUpdate(BaseModel):
    """Admin updates a user's personal details and role."""

    full_name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    role_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "UserUpdate":
        if (
            self.full_name is None
            and self.email is None
            and self.role_id is None
        ):
            raise ValueError(
                "Provide at least one of 'full_name', 'email', or 'role_id'"
            )
        return self


class UserPostOut(BaseModel):
    id: uuid.UUID
    headline: str | None
    topic: str
    section: PostSection
    status: PostStatus
    updated_at: datetime


class UserListItem(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    is_active: bool
    is_pending: bool
    is_email_pending: bool
    post_count: int
    posts: list[UserPostOut]


class PaginatedUsers(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int
    pages: int
