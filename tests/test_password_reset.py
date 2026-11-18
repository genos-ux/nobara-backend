"""Tests for the forgot/reset password flow."""

import json
import uuid
from unittest.mock import patch

from nabora_crm.core.exceptions import EmailSendError
from nabora_crm.core.security import hash_password
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.users.models import User

GENERIC_MESSAGE = (
    "If an account with that email exists, a password reset link has been sent."
)


def _create_user(*, password: str = "oldpassword123", is_pending: bool = False):
    email = f"reset-{uuid.uuid4().hex}@test.example"
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.name == "contributor").first()
        user = User(
            full_name="Reset User",
            email=email,
            hashed_password="!pending" if is_pending else hash_password(password),
            role_id=role.id,
            is_active=True,
            is_pending=is_pending,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id), email
    finally:
        db.close()


def _request_reset(client, email: str):
    return client.post("/v1/auth/forgot-password", json={"email": email})


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_forgot_password_sends_email_for_active_user(mock_send, client):
    _, email = _create_user()

    response = _request_reset(client, email)

    assert response.status_code == 200, response.text
    assert response.json()["message"] == GENERIC_MESSAGE
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == email
    assert kwargs["reset_token"]


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_forgot_password_hides_unknown_email(mock_send, client):
    response = _request_reset(client, "nobody@test.example")

    assert response.status_code == 200, response.text
    assert response.json()["message"] == GENERIC_MESSAGE
    mock_send.assert_not_called()


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_forgot_password_skips_pending_user(mock_send, client):
    _, email = _create_user(is_pending=True)

    response = _request_reset(client, email)

    assert response.status_code == 200, response.text
    assert response.json()["message"] == GENERIC_MESSAGE
    mock_send.assert_not_called()


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_forgot_password_hides_email_send_failure(mock_send, client):
    _, email = _create_user()
    mock_send.side_effect = EmailSendError("Brevo down")

    response = _request_reset(client, email)

    assert response.status_code == 200, response.text
    assert response.json()["message"] == GENERIC_MESSAGE


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_reset_password_success_and_token_is_single_use(mock_send, client):
    _, email = _create_user(password="oldpassword123")
    _request_reset(client, email)
    token = mock_send.call_args.kwargs["reset_token"]

    response = client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "newpassword456"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Password reset successfully"

    old_login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "oldpassword123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "newpassword456"},
    )
    assert new_login.status_code == 200, new_login.text
    assert "access_token" in new_login.json()

    reused = client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "anotherpassword789"},
    )
    assert reused.status_code == 401


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_new_reset_request_invalidates_previous_token(mock_send, client):
    _, email = _create_user()
    _request_reset(client, email)
    first_token = mock_send.call_args.kwargs["reset_token"]
    _request_reset(client, email)
    second_token = mock_send.call_args.kwargs["reset_token"]

    first = client.post(
        "/v1/auth/reset-password",
        json={"token": first_token, "new_password": "newpassword456"},
    )
    assert first.status_code == 401

    second = client.post(
        "/v1/auth/reset-password",
        json={"token": second_token, "new_password": "newpassword456"},
    )
    assert second.status_code == 200, second.text


@patch("nabora_crm.modules.auth.service.send_password_reset_email")
def test_reset_password_rejects_same_password(mock_send, client):
    _, email = _create_user(password="samepassword123")
    _request_reset(client, email)
    token = mock_send.call_args.kwargs["reset_token"]

    response = client.post(
        "/v1/auth/reset-password",
        json={"token": token, "new_password": "samepassword123"},
    )
    assert response.status_code == 400
    assert "different" in response.json()["detail"]


def test_reset_email_links_to_frontend_forgot_password(monkeypatch):
    from nabora_crm.core import email as email_module

    payloads: dict[str, dict] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b""

    def fake_urlopen(req, timeout):
        payloads["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(email_module.settings, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(email_module.urllib.request, "urlopen", fake_urlopen)

    email_module.send_password_reset_email(
        to_email="user@test.example",
        reset_token="token123",
    )

    text = payloads["body"]["textContent"]
    assert "/dashboard/forgot-password?token=token123" in text


def test_reset_password_rejects_invalid_token(client):
    response = client.post(
        "/v1/auth/reset-password",
        json={"token": "garbage-token", "new_password": "newpassword456"},
    )
    assert response.status_code == 401


def test_reset_password_rejects_short_password(client):
    response = client.post(
        "/v1/auth/reset-password",
        json={"token": "garbage-token", "new_password": "short"},
    )
    assert response.status_code == 422
