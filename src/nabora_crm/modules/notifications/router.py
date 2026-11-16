import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from nabora_crm.core.config import settings
from nabora_crm.core.security import create_stream_ticket
from nabora_crm.db.session import SessionLocal, get_db
from nabora_crm.modules.auth.dependencies import (
    get_current_user,
    resolve_stream_ticket,
)
from nabora_crm.modules.notifications.broker import notification_broker
from nabora_crm.modules.notifications.repository import (
    count_notifications,
    count_unread,
    get_notification,
    list_notifications,
    list_notifications_after,
    mark_all_notifications_read,
    mark_notification_read,
)
from nabora_crm.modules.notifications.schemas import (
    MarkAllReadOut,
    NotificationOut,
    PaginatedNotifications,
    StreamTicketOut,
    UnreadCountOut,
)
from nabora_crm.modules.notifications.service import notification_payload
from nabora_crm.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _format_sse(event: str, data: dict, event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


@router.get("", response_model=PaginatedNotifications)
def get_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedNotifications:
    """List the current user's notifications, newest first."""
    notifications = list_notifications(
        db,
        user_id=current_user.id,
        unread_only=unread_only,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    total = count_notifications(
        db,
        user_id=current_user.id,
        unread_only=unread_only,
    )
    unread_count = count_unread(db, user_id=current_user.id)
    pages = (total + page_size - 1) // page_size
    return PaginatedNotifications(
        items=[
            NotificationOut.model_validate(notification)
            for notification in notifications
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountOut:
    """Return the current user's unread notification count."""
    return UnreadCountOut(count=count_unread(db, user_id=current_user.id))


@router.post("/read-all", response_model=MarkAllReadOut)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MarkAllReadOut:
    """Mark all of the current user's notifications as read."""
    updated = mark_all_notifications_read(db, user_id=current_user.id)
    return MarkAllReadOut(updated=updated)


@router.post("/stream-ticket", response_model=StreamTicketOut)
def create_sse_ticket(
    current_user: User = Depends(get_current_user),
) -> StreamTicketOut:
    """Issue a short-lived ticket for opening the SSE stream.

    EventSource cannot send an Authorization header, so clients exchange their
    normal Bearer token for this short-lived ticket first.
    """
    return StreamTicketOut(
        ticket=create_stream_ticket(current_user.id, current_user.email),
        expires_in_seconds=settings.SSE_TICKET_EXPIRE_SECONDS,
    )


@router.get("/stream")
def stream_notifications(
    request: Request,
    ticket: str = Query(...),
) -> StreamingResponse:
    """Stream live notifications for the authenticated user over SSE."""
    with SessionLocal() as db:
        user = resolve_stream_ticket(db, ticket)
        user_id = user.id
        unread_count = count_unread(db, user_id=user_id)

        initial: list = []
        last_event_id = request.headers.get("last-event-id")
        if last_event_id:
            try:
                last_uuid = uuid.UUID(last_event_id)
            except ValueError:
                last_uuid = None
            if last_uuid is not None:
                last = get_notification(
                    db,
                    notification_id=last_uuid,
                    user_id=user_id,
                )
                if last is not None:
                    initial = list_notifications_after(
                        db,
                        user_id=user_id,
                        after=last.created_at,
                    )

    async def event_stream():
        queue = notification_broker.subscribe(user_id)
        try:
            yield _format_sse("connected", {"unread_count": unread_count})
            for notification in initial:
                yield _format_sse(
                    "notification",
                    notification_payload(notification),
                    event_id=str(notification.id),
                )

            while True:
                try:
                    payload = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.SSE_HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    continue
                yield _format_sse(
                    "notification",
                    payload,
                    event_id=str(payload.get("id")),
                )
        finally:
            notification_broker.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationOut:
    """Mark one of the current user's notifications as read."""
    notification = get_notification(
        db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification = mark_notification_read(db, notification)
    return NotificationOut.model_validate(notification)
