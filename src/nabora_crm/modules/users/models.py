import uuid

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nabora_crm.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Invitation state: True until the user sets their own password
    is_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    role: Mapped["Role"] = relationship(lazy="selectin")  # noqa: F821

    @property
    def permissions(self) -> list[str]:
        """Return permission names from the loaded role's permissions."""
        if self.role and self.role.permissions:
            return [p.name for p in self.role.permissions]
        return []
