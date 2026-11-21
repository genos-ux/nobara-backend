"""Tests for encryption at rest and decrypted API responses."""

import pytest
from sqlalchemy import text

from nabora_crm.core.encryption import (
    EncryptionError,
    decrypt,
    decrypt_deterministic,
    encrypt,
    encrypt_deterministic,
)
from nabora_crm.db.session import SessionLocal


def test_fernet_roundtrip_is_randomized():
    first = encrypt("sensitive value")
    second = encrypt("sensitive value")

    assert first != second
    assert first.startswith("enc:v1:")
    assert decrypt(first) == "sensitive value"
    assert decrypt(second) == "sensitive value"
    assert encrypt(None) is None
    assert decrypt(None) is None


def test_deterministic_roundtrip_is_stable():
    first = encrypt_deterministic("jane@example.com")
    second = encrypt_deterministic("jane@example.com")

    assert first == second
    assert first.startswith("siv:v1:")
    assert first != "jane@example.com"
    assert decrypt_deterministic(first) == "jane@example.com"
    assert encrypt_deterministic(None) is None
    assert decrypt_deterministic(None) is None


def test_decrypt_rejects_plaintext_and_corrupted_values():
    with pytest.raises(EncryptionError):
        decrypt("not encrypted")

    with pytest.raises(EncryptionError):
        decrypt("enc:v1:this-is-not-a-valid-token")

    with pytest.raises(EncryptionError):
        decrypt_deterministic("siv:v1:not-base64!")


def test_raw_database_stores_ciphertext(client):
    email = "encrypted.visitor@test.example"
    name = "Encrypted Visitor"
    subject = "Encrypted subject line"
    message = "This message must not appear in the raw database."

    resp = client.post(
        "/v1/contact-messages",
        json={
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
        },
    )
    assert resp.status_code == 201, resp.text

    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    assert login.status_code == 200, login.text
    body = resp.json()
    assert body["name"] == name
    assert body["email"] == email
    assert body["subject"] == subject
    assert body["message"] == message

    db = SessionLocal()
    try:
        raw_person = db.execute(
            text("SELECT name, email FROM persons WHERE email = :email"),
            {"email": encrypt_deterministic(email)},
        ).one()
        assert raw_person.email.startswith("siv:v1:")
        assert raw_person.email != email
        assert raw_person.name.startswith("enc:v1:")
        assert raw_person.name != name

        rows = db.execute(
            text("SELECT subject, description FROM activities")
        ).fetchall()
        matching = [row for row in rows if decrypt(row.subject) == subject]
        assert len(matching) == 1
        assert matching[0].subject.startswith("enc:v1:")
        assert matching[0].description.startswith("enc:v1:")
        assert matching[0].description != message

        raw_admin = db.execute(
            text("SELECT email FROM users WHERE email = :email"),
            {"email": encrypt_deterministic("admin@test.example")},
        ).one()
        assert raw_admin.email.startswith("siv:v1:")
        assert raw_admin.email != "admin@test.example"

        audit_rows = db.execute(
            text("SELECT actor_email, detail FROM audit_logs")
        ).fetchall()
        assert audit_rows
        for row in audit_rows:
            if row.actor_email is not None:
                assert row.actor_email.startswith("enc:v1:")
            if row.detail is not None:
                assert row.detail.startswith("enc:v1:")

        notification_rows = db.execute(
            text("SELECT title, message FROM notifications")
        ).fetchall()
        assert notification_rows
        for row in notification_rows:
            assert row.title.startswith("enc:v1:")
            assert row.message.startswith("enc:v1:")
    finally:
        db.close()


def test_email_uniqueness_is_preserved(client):
    email = "unique.encrypted@test.example"
    payload = {
        "name": "Unique Person",
        "email": email,
        "subject": "First",
        "message": "First message",
    }

    first = client.post("/v1/contact-messages", json=payload)
    second = client.post(
        "/v1/contact-messages",
        json={**payload, "subject": "Second", "message": "Second message"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["person_id"] == second.json()["person_id"]

    db = SessionLocal()
    try:
        count = db.execute(
            text("SELECT COUNT(*) FROM persons WHERE email = :email"),
            {"email": encrypt_deterministic(email)},
        ).scalar_one()
        assert count == 1
    finally:
        db.close()
