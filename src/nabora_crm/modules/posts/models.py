import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nabora_crm.db.base import Base


class PostSection(enum.Enum):
    nutrition = "nutrition"
    fitness = "fitness"


class PostStatus(enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    unpublished = "unpublished"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    headline: Mapped[str | None] = mapped_column(String, nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    practical_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    sources_references: Mapped[str | None] = mapped_column(Text, nullable=True)

    section: Mapped[PostSection] = mapped_column(
        Enum(PostSection, name="post_section"), nullable=False, index=True,
    )
    topic: Mapped[str] = mapped_column(String, nullable=False, index=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    placeholder_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status"),
        nullable=False,
        default=PostStatus.draft,
        index=True,
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    author: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    @property
    def author_email(self) -> str | None:
        return self.author.email if self.author else None
