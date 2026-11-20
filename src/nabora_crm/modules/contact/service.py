from sqlalchemy.orm import Session

from nabora_crm.modules.audit.models import AuditAction
from nabora_crm.modules.audit.service import log_action
from nabora_crm.modules.contact.repository import (
    count_contact_activities,
    create_contact_activity,
    create_person,
    get_person_by_email,
    list_contact_activities,
    set_person_name,
)
from nabora_crm.modules.contact.schemas import ContactCreate
from nabora_crm.modules.crm.models import Activity, Person


def _get_or_create_person(db: Session, payload: ContactCreate) -> Person:
    """Return the person for this email, creating or naming them as needed.

    A name that staff already set is never overwritten; we only fill in a
    missing name.
    """
    person = get_person_by_email(db, payload.email)
    if person is None:
        return create_person(db, name=payload.name, email=payload.email)
    if not person.name and payload.name:
        return set_person_name(db, person, payload.name)
    return person


def submit_contact_message(db: Session, *, payload: ContactCreate) -> Activity:
    """Save a public contact form submission as a CRM activity (no email sent)."""
    person = _get_or_create_person(db, payload)
    activity = create_contact_activity(
        db,
        person_id=person.id,
        subject=payload.subject,
        message=payload.message,
    )
    log_action(
        db,
        action=AuditAction.CONTACT_RECEIVED,
        actor_email=payload.email,
        resource_type="person",
        resource_id=str(person.id),
        detail=(
            f'Contact form "{payload.subject}" submitted by '
            f"{payload.name} <{payload.email}>."
        ),
    )
    return activity


def list_contact_messages(
    db: Session,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> tuple[list[Activity], int]:
    """Return saved contact messages newest first, with the total count."""
    activities = list_contact_activities(db, offset=offset, limit=limit)
    total = count_contact_activities(db)
    return activities, total
