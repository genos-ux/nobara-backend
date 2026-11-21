import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nabora_crm.core.encryption import (
    DeterministicEncryptedString,
    EncryptedString,
)
from nabora_crm.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    email: Mapped[str] = mapped_column(
        DeterministicEncryptedString, unique=True, nullable=False, index=True,
    )
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Invitation state: True until the user sets their own password
    is_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Email invitation state: True until the user sets their own password,
    # then flipped to False to signal the invitation email is no longer pending.
    is_email_pending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Incremented every time an invitation is (re)sent. Tokens carry the
    # version they were issued for, so older links stop working on resend.
    invitation_token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Incremented when a password reset is requested and again after it is used,
    # so older reset links stop working.
    password_reset_token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    role: Mapped["Role"] = relationship(lazy="selectin")  # noqa: F821

    @property
    def permissions(self) -> list[str]:
        """Return permission names from the loaded role's permissions."""
        if self.role and self.role.permissions:
            return [p.name for p in self.role.permissions]
        return []
