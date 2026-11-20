"""Tests for the public contact form endpoints."""

from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.crm.models import Activity, Person
from nabora_crm.modules.contact.repository import CONTACT_FORM_ACTIVITY_TYPE


def _payload(**overrides) -> dict:
    data = {
        "name": "Visitor Person",
        "email": "visitor1@test.example",
        "subject": "Question about plans",
        "message": "I would like to know more about your services.",
    }
    data.update(overrides)
    return data


def _login(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_guest_can_submit_contact_message(client):
    resp = client.post("/v1/contact-messages", json=_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "visitor1@test.example"
    assert body["subject"] == "Question about plans"
    assert body["message"] == "I would like to know more about your services."
    assert body["person_id"]

    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.email == "visitor1@test.example").one()
        activity = (
            db.query(Activity)
            .filter(
                Activity.person_id == person.id,
                Activity.activity_type == CONTACT_FORM_ACTIVITY_TYPE,
            )
            .one()
        )
        assert activity.subject == "Question about plans"
        assert activity.description == "I would like to know more about your services."
        assert activity.staff_name is None
    finally:
        db.close()


def test_repeat_submission_reuses_person_and_adds_activity(client):
    email = "visitor5@test.example"
    first = client.post("/v1/contact-messages", json=_payload(email=email))
    assert first.status_code == 201, first.text

    second = client.post(
        "/v1/contact-messages",
        json=_payload(
            email=email,
            subject="Second question",
            message="Another message.",
        ),
    )
    assert second.status_code == 201, second.text
    assert second.json()["person_id"] == first.json()["person_id"]

    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.email == "visitor5@test.example").one()
        count = (
            db.query(Activity)
            .filter(
                Activity.person_id == person.id,
                Activity.activity_type == CONTACT_FORM_ACTIVITY_TYPE,
            )
            .count()
        )
        assert count == 2
    finally:
        db.close()


def test_existing_person_name_is_not_overwritten(client):
    db = SessionLocal()
    try:
        db.add(
            Person(
                name="Staff Set Name",
                email="visitor2@test.example",
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/v1/contact-messages",
        json=_payload(name="Different Name", email="visitor2@test.example"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Staff Set Name"

    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.email == "visitor2@test.example").one()
        assert person.name == "Staff Set Name"
    finally:
        db.close()


def test_missing_person_name_is_filled_from_submission(client):
    db = SessionLocal()
    try:
        db.add(Person(name=None, email="visitor3@test.example"))
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/v1/contact-messages",
        json=_payload(name="Filled Name", email="visitor3@test.example"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Filled Name"

    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.email == "visitor3@test.example").one()
        assert person.name == "Filled Name"
    finally:
        db.close()


def test_contact_message_validation(client):
    bad_email = client.post(
        "/v1/contact-messages",
        json=_payload(email="not-an-email"),
    )
    assert bad_email.status_code == 422

    blank_subject = client.post(
        "/v1/contact-messages",
        json=_payload(subject="   "),
    )
    assert blank_subject.status_code == 422

    missing_message = client.post(
        "/v1/contact-messages",
        json={k: v for k, v in _payload().items() if k != "message"},
    )
    assert missing_message.status_code == 422


def test_listing_requires_authentication(client):
    resp = client.get("/v1/contact-messages")
    assert resp.status_code in (401, 403)


def test_admin_can_list_contact_messages(client):
    create = client.post(
        "/v1/contact-messages",
        json=_payload(
            name="Listed Customer",
            email="visitor4@test.example",
            message="Listed message body.",
        ),
    )
    assert create.status_code == 201, create.text

    headers = _login(client, "admin@test.example", "testpass123")
    resp = client.get("/v1/contact-messages", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    item = next(
        item for item in body["items"] if item["email"] == "visitor4@test.example"
    )
    assert item == {
        "name": "Listed Customer",
        "email": "visitor4@test.example",
        "message": "Listed message body.",
    }


def test_contact_messages_list_pagination(client):
    headers = _login(client, "admin@test.example", "testpass123")

    first = client.get(
        "/v1/contact-messages?page=1&page_size=1",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["page"] == 1
    assert first_body["page_size"] == 1
    assert len(first_body["items"]) == 1

    if first_body["pages"] > 1:
        second = client.get(
            "/v1/contact-messages?page=2&page_size=1",
            headers=headers,
        )
        assert second.status_code == 200, second.text
        assert second.json()["page"] == 2
        assert len(second.json()["items"]) == 1
