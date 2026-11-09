import uuid
from datetime import datetime

from pydantic import BaseModel

from nabora_crm.modules.posts.models import PostSection, PostStatus


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    is_active: bool


class ContributorPostOut(BaseModel):
    id: uuid.UUID
    headline: str | None
    topic: str
    section: PostSection
    status: PostStatus
    updated_at: datetime


class ContributorOut(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    is_active: bool
    is_pending: bool
    post_count: int
    posts: list[ContributorPostOut]


class PaginatedContributors(BaseModel):
    items: list[ContributorOut]
    total: int
    page: int
    page_size: int
    pages: int
