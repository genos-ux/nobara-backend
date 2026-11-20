from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import CRM_READ
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.contact.schemas import (
    ContactCreate,
    ContactCustomerOut,
    ContactMessageOut,
    PaginatedContactCustomers,
)
from nabora_crm.modules.contact.service import (
    list_contact_messages,
    submit_contact_message,
)
from nabora_crm.modules.crm.models import Activity
from nabora_crm.modules.users.models import User

router = APIRouter(prefix="/contact-messages", tags=["contact"])


def _to_out(activity: Activity) -> ContactMessageOut:
    person = activity.person
    return ContactMessageOut(
        id=activity.id,
        person_id=activity.person_id,
        name=person.name,
        email=person.email,
        subject=activity.subject,
        message=activity.description,
        created_at=activity.created_at,
    )


@router.post("", response_model=ContactMessageOut, status_code=201)
def submit_contact_message_endpoint(
    payload: ContactCreate,
    db: Session = Depends(get_db),
) -> ContactMessageOut:
    """Save a contact form submission from a visitor. No authentication needed."""
    activity = submit_contact_message(db, payload=payload)
    return _to_out(activity)


@router.get("", response_model=PaginatedContactCustomers)
def list_contact_messages_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(CRM_READ)),
) -> PaginatedContactCustomers:
    """List contact form submitters with their message (requires `crm:read`)."""
    messages, total = list_contact_messages(
        db,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return PaginatedContactCustomers(
        items=[
            ContactCustomerOut(
                name=message.person.name,
                email=message.person.email,
                message=message.description,
            )
            for message in messages
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
