import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactCreate(BaseModel):
    """Payload submitted by a visitor through the public contact form."""

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)

    @field_validator("name", "subject", "message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ContactMessageOut(BaseModel):
    """A saved contact form submission, joined with its CRM person."""

    id: uuid.UUID
    person_id: uuid.UUID
    name: str | None
    email: str
    subject: str | None
    message: str
    created_at: datetime


class ContactCustomerOut(BaseModel):
    """A contact form submitter with their message."""

    name: str | None
    email: str
    message: str


class PaginatedContactCustomers(BaseModel):
    items: list[ContactCustomerOut]
    total: int
    page: int
    page_size: int
    pages: int
