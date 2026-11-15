import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from nabora_crm.modules.posts.models import PostSection, PostStatus, PostTopic

# Request schemas use inlined Literal enums so Swagger UI renders native
# dropdowns for these fields. Keep them in sync with the model enums above.
PostSectionValue = Literal[*(member.value for member in PostSection)]
PostTopicValue = Literal[*(member.value for member in PostTopic)]

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
    section: PostSectionValue
    topic: PostTopicValue
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
    section: PostSectionValue | None = None
    topic: PostTopicValue | None = None
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
    topic: PostTopic
    image_url: str | None
    placeholder_color: str | None
    status: PostStatus
    author_id: uuid.UUID
    author_email: str | None
    created_at: datetime
    updated_at: datetime


class PostListItem(PostOut):
    """A post in a list, including all post details.

    ``title`` and ``author`` mirror ``headline`` and ``author_email`` for
    backwards compatibility with existing clients.
    """

    title: str | None
    author: str | None
    author_name: str | None = None


class PaginatedPosts(BaseModel):
    items: list[PostListItem]
    total: int
    page: int
    page_size: int
    pages: int


class PostStatusCounts(BaseModel):
    draft: int
    pending_review: int
    published: int
    unpublished: int
    total: int
