import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from nabora_crm.modules.posts.models import PostSection, PostStatus

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _validate_hex_color(value: str | None) -> str | None:
    if value is None:
        return None
    if not HEX_COLOR_RE.match(value):
        raise ValueError("placeholder_color must be a hex code like #fff or #ffffff")
    return value


class PostCreate(BaseModel):
    headline: str | None = None
    introduction: str | None = None
    evidence_explanation: str | None = None
    practical_guidance: str = Field(min_length=1)
    sources_references: str | None = None
    section: PostSection
    topic: str = Field(min_length=1)
    image_url: HttpUrl | None = None
    placeholder_color: str | None = None
    status: PostStatus = PostStatus.draft

    _check_color = field_validator("placeholder_color")(_validate_hex_color)

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: PostStatus) -> PostStatus:
        if value not in (PostStatus.draft, PostStatus.pending_review):
            raise ValueError("status must be 'draft' or 'pending_review'")
        return value


class PostUpdate(BaseModel):
    headline: str | None = None
    introduction: str | None = None
    evidence_explanation: str | None = None
    practical_guidance: str | None = Field(default=None, min_length=1)
    sources_references: str | None = None
    section: PostSection | None = None
    topic: str | None = Field(default=None, min_length=1)
    image_url: HttpUrl | None = None
    placeholder_color: str | None = None

    _check_color = field_validator("placeholder_color")(_validate_hex_color)


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    headline: str | None
    introduction: str | None
    evidence_explanation: str | None
    practical_guidance: str
    sources_references: str | None
    section: PostSection
    topic: str
    image_url: str | None
    placeholder_color: str | None
    status: PostStatus
    author_id: uuid.UUID
    author_email: str | None
    created_at: datetime
    updated_at: datetime


class PostListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    author: str | None
    topic: str
    status: PostStatus
    updated_at: datetime


class PaginatedPosts(BaseModel):
    items: list[PostListItem]
    total: int
    page: int
    page_size: int
    pages: int
