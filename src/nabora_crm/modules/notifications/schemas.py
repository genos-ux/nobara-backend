import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    message: str
    post_id: uuid.UUID | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class PaginatedNotifications(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    page_size: int
    pages: int
    unread_count: int


class UnreadCountOut(BaseModel):
    count: int


class MarkAllReadOut(BaseModel):
    updated: int


class StreamTicketOut(BaseModel):
    ticket: str
    expires_in_seconds: int
