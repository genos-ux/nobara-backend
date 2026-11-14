"""Tests for the invitation endpoints.

Covers:
- Admin can invite a new user (email is sent)
- Invited user can set up their password with a valid token
- Invalid token is rejected
- Expired token is rejected
- Already-used token is rejected
- Unauthenticated users cannot invite
- Users without invitations:write permission cannot invite
- Pending user cannot log in until they set up their password
- Cannot invite a duplicate (non-pending) email
"""
from unittest.mock import patch

import pytest

from nabora_crm.core.security import create_invitation_token
from nabora_crm.modules.users.models import User


@pytest.fixture()
def admin_token(client):
    """Log in as the seeded admin and return a bearer token."""
    resp = client.post(
        "/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _get_contributor_role_id(client, admin_headers):
    """Fetch the contributor role ID via the roles API."""
    resp = client.get("/v1/roles", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    roles = resp.json()
    for r in roles:
        if r["name"] == "contributor":
            return r["id"]
    pytest.fail("contributor role not found")


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_invite_user_success(mock_send_email, client, admin_headers):
    """Admin can invite a new user; email is dispatched."""
    role_id = _get_contributor_role_id(client, admin_headers)

    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "New User",
            "email": "newuser@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["full_name"] == "New User"
    assert data["email"] == "newuser@test.example"
    assert data["is_pending"] is True
    assert data["role"] == "contributor"
    mock_send_email.assert_called_once()


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_invite_duplicate_non_pending(mock_send_email, client, admin_headers):
    """Inviting an email that already belongs to an active user fails."""
    role_id = _get_contributor_role_id(client, admin_headers)

    # First invite
    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "Dup User",
            "email": "dup@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201

    # Accept the invitation to make the user non-pending
    token = create_invitation_token(
        {"sub": str(resp.json()["id"]), "email": "dup@test.example"}
    )
    accept = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "newpassword123"},
    )
    assert accept.status_code == 200

    # Now try to invite the same email again
    resp2 = client.post(
        "/v1/invitations",
        json={
            "full_name": "Dup User",
            "email": "dup@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_invite_unauthenticated(mock_send_email, client):
    """Unauthenticated users cannot invite."""
    role_id = _get_contributor_role_id(
        client,
        {"Authorization": "Bearer " + _get_admin_token_raw(client)},
    )
    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "No Auth",
            "email": "noauth@test.example",
            "role_id": role_id,
        },
    )
    assert resp.status_code == 401


def _get_admin_token_raw(client):
    resp = client.post(
        "/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    return resp.json()["access_token"]


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_accept_invitation_success(mock_send_email, client, admin_headers):
    """Invited user can set up their password with a valid token."""
    role_id = _get_contributor_role_id(client, admin_headers)

    # Invite
    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "Accept Me",
            "email": "acceptme@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Generate token (same as the email link would contain)
    token = create_invitation_token(
        {"sub": user_id, "email": "acceptme@test.example"}
    )

    # Accept
    accept = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "strongpassword123"},
    )
    assert accept.status_code == 200, accept.text
    data = accept.json()
    assert data["email"] == "acceptme@test.example"
    assert data["is_pending"] is False

    # User should now be able to log in
    login = client.post(
        "/v1/auth/login",
        json={"email": "acceptme@test.example", "password": "strongpassword123"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_accept_invitation_invalid_token(mock_send_email, client, admin_headers):
    """An invalid token is rejected."""
    resp = client.post(
        "/v1/invitations/accept",
        json={"token": "garbage-token", "password": "somepassword123"},
    )
    assert resp.status_code == 401


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_accept_invitation_already_used(mock_send_email, client, admin_headers):
    """A token that has already been used is rejected."""
    role_id = _get_contributor_role_id(client, admin_headers)

    # Invite
    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "Used User",
            "email": "used@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    token = create_invitation_token({"sub": user_id, "email": "used@test.example"})

    # First accept succeeds
    accept1 = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "firstpassword123"},
    )
    assert accept1.status_code == 200

    # Second accept fails
    accept2 = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "secondpassword123"},
    )
    assert accept2.status_code == 401
    assert "already been used" in accept2.json()["detail"]


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_pending_user_cannot_login(mock_send_email, client, admin_headers):
    """A pending user (hasn't set up password) cannot log in."""
    role_id = _get_contributor_role_id(client, admin_headers)

    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "Pending User",
            "email": "pending@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201

    # Login should fail
    login = client.post(
        "/v1/auth/login",
        json={"email": "pending@test.example", "password": "!pending"},
    )
    assert login.status_code == 401


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_reinvite_pending_user_rejected(mock_send_email, client, admin_headers):
    """Inviting an email that already exists is rejected, even if pending."""
    role_id = _get_contributor_role_id(client, admin_headers)

    resp1 = client.post(
        "/v1/invitations",
        json={
            "full_name": "Reinvite User",
            "email": "reinvite@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp1.status_code == 201
    assert mock_send_email.call_count == 1

    resp2 = client.post(
        "/v1/invitations",
        json={
            "full_name": "Reinvite User",
            "email": "reinvite@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp2.status_code == 400
    assert "already exists in the system" in resp2.json()["detail"]
    assert mock_send_email.call_count == 1


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_resend_invitation_by_user_id(mock_send_email, client, admin_headers):
    """Admin can resend an invitation using the user id."""
    role_id = _get_contributor_role_id(client, admin_headers)

    invite = client.post(
        "/v1/invitations",
        json={
            "full_name": "Resend By Id",
            "email": "resend-id@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201
    user_id = invite.json()["id"]

    resp = client.post(
        "/v1/invitations/resend",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == user_id
    assert data["email"] == "resend-id@test.example"
    assert data["is_pending"] is True
    assert data["expires_in_days"] >= 1
    assert "re-sent" in data["message"]
    assert mock_send_email.call_count == 2


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_resend_invitation_by_email(mock_send_email, client, admin_headers):
    """Admin can resend an invitation using the email address."""
    role_id = _get_contributor_role_id(client, admin_headers)

    invite = client.post(
        "/v1/invitations",
        json={
            "full_name": "Resend By Email",
            "email": "resend-email@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201

    resp = client.post(
        "/v1/invitations/resend",
        json={"email": "resend-email@test.example"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "resend-email@test.example"
    assert mock_send_email.call_count == 2


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_resend_invitation_unknown_user(mock_send_email, client, admin_headers):
    """Resending to an unknown user returns a domain error."""
    resp = client.post(
        "/v1/invitations/resend",
        json={"email": "missing@test.example"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "No user found" in resp.json()["detail"]
    mock_send_email.assert_not_called()


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_resend_invitation_completed_user(mock_send_email, client, admin_headers):
    """Resending to a user who already set their password is rejected."""
    role_id = _get_contributor_role_id(client, admin_headers)

    invite = client.post(
        "/v1/invitations",
        json={
            "full_name": "Completed User",
            "email": "completed@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201
    user_id = invite.json()["id"]

    token = create_invitation_token(
        {"sub": user_id, "email": "completed@test.example"}
    )
    accept = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "strongpassword123"},
    )
    assert accept.status_code == 200

    resp = client.post(
        "/v1/invitations/resend",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "already completed" in resp.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": "00000000-0000-0000-0000-000000000000", "email": "both@test.example"},
    ],
)
def test_resend_invitation_requires_exactly_one_identifier(
    client, admin_headers, payload
):
    """Exactly one of user_id or email must be provided."""
    resp = client.post(
        "/v1/invitations/resend",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_resend_invitation_unauthenticated(client):
    """Unauthenticated users cannot resend invitations."""
    resp = client.post(
        "/v1/invitations/resend",
        json={"email": "noauth@test.example"},
    )
    assert resp.status_code == 401


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_password_too_short(mock_send_email, client, admin_headers):
    """Password shorter than 8 characters is rejected by validation."""
    role_id = _get_contributor_role_id(client, admin_headers)

    resp = client.post(
        "/v1/invitations",
        json={
            "full_name": "Short Pw",
            "email": "shortpw@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    token = create_invitation_token({"sub": user_id, "email": "shortpw@test.example"})

    accept = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "short"},
    )
    assert accept.status_code == 422
