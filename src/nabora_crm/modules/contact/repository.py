import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from nabora_crm.modules.crm.models import Activity, Person

CONTACT_FORM_ACTIVITY_TYPE = "contact_form"


def get_person_by_email(db: Session, email: str) -> Person | None:
    """Fetch a CRM person by email address."""
    stmt = select(Person).where(Person.email == email)
    return db.execute(stmt).scalar_one_or_none()


def create_person(db: Session, *, name: str | None, email: str) -> Person:
    """Create and persist a CRM person for a contact form visitor."""
    person = Person(name=name, email=email)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def set_person_name(db: Session, person: Person, name: str) -> Person:
    """Fill in a person's name when it is currently missing."""
    person.name = name
    db.commit()
    db.refresh(person)
    return person


def create_contact_activity(
    db: Session,
    *,
    person_id: uuid.UUID,
    subject: str,
    message: str,
) -> Activity:
    """Persist a contact form submission as a CRM activity."""
    activity = Activity(
        person_id=person_id,
        activity_type=CONTACT_FORM_ACTIVITY_TYPE,
        subject=subject,
        description=message,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _contact_conditions() -> list:
    return [Activity.activity_type == CONTACT_FORM_ACTIVITY_TYPE]


def list_contact_activities(
    db: Session,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[Activity]:
    """List contact form submissions newest first, loading their person."""
    stmt = (
        select(Activity)
        .where(*_contact_conditions())
        .options(selectinload(Activity.person))
        .order_by(Activity.created_at.desc())
    )
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_contact_activities(db: Session) -> int:
    """Count saved contact form submissions."""
    stmt = (
        select(func.count())
        .select_from(Activity)
        .where(*_contact_conditions())
    )
    return db.execute(stmt).scalar_one()
