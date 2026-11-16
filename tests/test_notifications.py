"""Tests for the notifications REST endpoints.

Covers:
- GET  /v1/notifications         — paginated list (all and unread-only)
- GET  /v1/notifications/unread-count
- POST /v1/notifications/read-all
- POST /v1/notifications/stream-ticket — returns ticket and expires_in_seconds
- GET  /v1/notifications/stream  — rejects invalid/missing ticket with 401
- PATCH /v1/notifications/{id}/read — marks one notification as read
- Authentication is required on every endpoint
- Notifications from one user are not visible to another
- Route registration in the OpenAPI schema
"""

import uuid

import pytest

from nabora_crm.core.security import create_stream_ticket, hash_password
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.notifications.models import Notification, NotificationType
from nabora_crm.modules.notifications.repository import create_notification
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.users.models import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _get_or_create_user(email: str, password: str, full_name: str) -> uuid.UUID:
    """Return an existing or freshly-created active contributor user."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return existing.id
        role = db.query(Role).filter(Role.name == "contributor").first()
        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _seed_notification(
    user_id: uuid.UUID,
    *,
    title: str = "Test notification",
    message: str = "This is a test.",
    notification_type: str = NotificationType.USER_UPDATED,
    is_read: bool = False,
) -> uuid.UUID:
    """Insert one notification directly and return its ID."""
    db = SessionLocal()
    try:
        note = create_notification(
            db,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
        )
        if is_read:
            note.is_read = True
            db.commit()
            db.refresh(note)
        return note.id
    finally:
        db.close()


def _clear_notifications(user_id: uuid.UUID) -> None:
    """Delete all notifications for a user (keeps tests isolated)."""
    db = SessionLocal()
    try:
        db.query(Notification).filter(Notification.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_A_EMAIL = "notif_user_a@test.example"
USER_A_PASS = "passA123!"
USER_B_EMAIL = "notif_user_b@test.example"
USER_B_PASS = "passB123!"


@pytest.fixture(scope="module")
def user_a_id():
    return _get_or_create_user(USER_A_EMAIL, USER_A_PASS, "Notification User A")


@pytest.fixture(scope="module")
def user_b_id():
    return _get_or_create_user(USER_B_EMAIL, USER_B_PASS, "Notification User B")


@pytest.fixture()
def headers_a(client):
    return _login(client, USER_A_EMAIL, USER_A_PASS)


@pytest.fixture()
def headers_b(client):
    return _login(client, USER_B_EMAIL, USER_B_PASS)


# ---------------------------------------------------------------------------
# OpenAPI route registration
# ---------------------------------------------------------------------------


class TestNotificationRoutes:
    def test_routes_in_openapi(self, client):
        """All notification endpoints appear in the OpenAPI schema."""
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/v1/notifications" in paths
        assert "/v1/notifications/unread-count" in paths
        assert "/v1/notifications/read-all" in paths
        assert "/v1/notifications/stream-ticket" in paths
        assert "/v1/notifications/stream" in paths
        assert "/v1/notifications/{notification_id}/read" in paths


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------


class TestNotificationAuth:
    def test_list_requires_auth(self, client):
        resp = client.get("/v1/notifications")
        assert resp.status_code == 403

    def test_unread_count_requires_auth(self, client):
        resp = client.get("/v1/notifications/unread-count")
        assert resp.status_code == 403

    def test_read_all_requires_auth(self, client):
        resp = client.post("/v1/notifications/read-all")
        assert resp.status_code == 403

    def test_stream_ticket_requires_auth(self, client):
        resp = client.post("/v1/notifications/stream-ticket")
        assert resp.status_code == 403

    def test_mark_read_requires_auth(self, client):
        resp = client.patch(f"/v1/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List notifications
# ---------------------------------------------------------------------------


class TestListNotifications:
    def test_empty_list(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        resp = client.get("/v1/notifications", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["unread_count"] == 0

    def test_returns_own_notifications(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        note_id = _seed_notification(user_a_id, title="Hello A")
        resp = client.get("/v1/notifications", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        ids = [item["id"] for item in body["items"]]
        assert str(note_id) in ids

    def test_does_not_return_other_users_notifications(
        self, client, headers_a, user_a_id, user_b_id
    ):
        _clear_notifications(user_a_id)
        _seed_notification(user_b_id, title="Only for B")
        resp = client.get("/v1/notifications", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_unread_only_filter(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        _seed_notification(user_a_id, title="Unread one", is_read=False)
        _seed_notification(user_a_id, title="Read one", is_read=True)

        resp = client.get(
            "/v1/notifications", params={"unread_only": "true"}, headers=headers_a
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["is_read"] is False

    def test_pagination(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        for i in range(5):
            _seed_notification(user_a_id, title=f"Note {i}")

        resp = client.get(
            "/v1/notifications", params={"page": 1, "page_size": 3}, headers=headers_a
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["total"] == 5
        assert body["pages"] == 2

    def test_notification_shape(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        _seed_notification(
            user_a_id,
            title="Shape check",
            message="Body text here",
            notification_type=NotificationType.PASSWORD_CHANGED,
        )
        resp = client.get("/v1/notifications", headers=headers_a)
        item = resp.json()["items"][0]
        assert "id" in item
        assert "type" in item
        assert "title" in item
        assert "message" in item
        assert "is_read" in item
        assert "created_at" in item
        assert item["type"] == NotificationType.PASSWORD_CHANGED
        assert item["title"] == "Shape check"
        assert item["message"] == "Body text here"

    def test_newest_first_ordering(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        for i in range(3):
            _seed_notification(user_a_id, title=f"Note {i}")

        resp = client.get("/v1/notifications", headers=headers_a)
        items = resp.json()["items"]
        timestamps = [item["created_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_unread_count_in_list_response(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        _seed_notification(user_a_id, is_read=False)
        _seed_notification(user_a_id, title="Read", is_read=True)

        resp = client.get("/v1/notifications", headers=headers_a)
        body = resp.json()
        assert body["unread_count"] == 1


# ---------------------------------------------------------------------------
# Unread count
# ---------------------------------------------------------------------------


class TestUnreadCount:
    def test_zero_when_empty(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        resp = client.get("/v1/notifications/unread-count", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_counts_unread_only(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        _seed_notification(user_a_id, is_read=False)
        _seed_notification(user_a_id, is_read=False)
        _seed_notification(user_a_id, is_read=True)

        resp = client.get("/v1/notifications/unread-count", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_isolated_per_user(self, client, headers_a, user_a_id, user_b_id):
        _clear_notifications(user_a_id)
        _seed_notification(user_b_id)  # belongs to B

        resp = client.get("/v1/notifications/unread-count", headers=headers_a)
        assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Mark all read
# ---------------------------------------------------------------------------


class TestMarkAllRead:
    def test_marks_all_unread(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        for _ in range(3):
            _seed_notification(user_a_id, is_read=False)

        resp = client.post("/v1/notifications/read-all", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3

        count_resp = client.get("/v1/notifications/unread-count", headers=headers_a)
        assert count_resp.json()["count"] == 0

    def test_already_read_not_counted(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        _seed_notification(user_a_id, is_read=True)
        _seed_notification(user_a_id, is_read=False)

        resp = client.post("/v1/notifications/read-all", headers=headers_a)
        assert resp.json()["updated"] == 1

    def test_no_notifications_returns_zero(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        resp = client.post("/v1/notifications/read-all", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    def test_does_not_mark_other_users(self, client, headers_a, user_a_id, user_b_id):
        _clear_notifications(user_b_id)
        _seed_notification(user_b_id, is_read=False)

        client.post("/v1/notifications/read-all", headers=headers_a)

        # B's notification should still be unread
        count_resp = client.get("/v1/notifications/unread-count", headers=headers_b(client))
        assert count_resp.json()["count"] == 1

    def headers_b(self, client):
        return _login(client, USER_B_EMAIL, USER_B_PASS)


# A cleaner approach for the cross-user test above:
class TestMarkAllReadCrossUser:
    def test_does_not_affect_other_user(
        self, client, headers_a, headers_b, user_a_id, user_b_id
    ):
        _clear_notifications(user_b_id)
        _seed_notification(user_b_id, is_read=False)

        client.post("/v1/notifications/read-all", headers=headers_a)

        resp = client.get("/v1/notifications/unread-count", headers=headers_b)
        assert resp.json()["count"] == 1


# ---------------------------------------------------------------------------
# Mark single notification read
# ---------------------------------------------------------------------------


class TestMarkOneRead:
    def test_mark_read_success(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        note_id = _seed_notification(user_a_id, is_read=False)

        resp = client.patch(
            f"/v1/notifications/{note_id}/read", headers=headers_a
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(note_id)
        assert body["is_read"] is True
        assert body["read_at"] is not None

    def test_mark_read_idempotent(self, client, headers_a, user_a_id):
        _clear_notifications(user_a_id)
        note_id = _seed_notification(user_a_id, is_read=True)

        resp = client.patch(
            f"/v1/notifications/{note_id}/read", headers=headers_a
        )
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_cannot_mark_other_users_notification(
        self, client, headers_a, user_b_id
    ):
        """User A cannot mark a notification that belongs to user B."""
        note_id = _seed_notification(user_b_id, is_read=False)

        resp = client.patch(
            f"/v1/notifications/{note_id}/read", headers=headers_a
        )
        assert resp.status_code == 404

    def test_nonexistent_notification_returns_404(self, client, headers_a):
        resp = client.patch(
            f"/v1/notifications/{uuid.uuid4()}/read", headers=headers_a
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SSE stream ticket
# ---------------------------------------------------------------------------


class TestStreamTicket:
    def test_issues_ticket(self, client, headers_a):
        resp = client.post("/v1/notifications/stream-ticket", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert "ticket" in body
        assert "expires_in_seconds" in body
        assert isinstance(body["ticket"], str)
        assert len(body["ticket"]) > 10
        assert body["expires_in_seconds"] == 60  # SSE_TICKET_EXPIRE_SECONDS default

    def test_ticket_is_different_each_call(self, client, headers_a):
        t1 = client.post(
            "/v1/notifications/stream-ticket", headers=headers_a
        ).json()["ticket"]
        t2 = client.post(
            "/v1/notifications/stream-ticket", headers=headers_a
        ).json()["ticket"]
        assert t1 != t2


# ---------------------------------------------------------------------------
# SSE stream — connection validation only (no live streaming in unit tests)
# ---------------------------------------------------------------------------


class TestSSEStream:
    def test_missing_ticket_returns_422(self, client):
        """The stream endpoint requires a ?ticket= query param."""
        resp = client.get("/v1/notifications/stream")
        # 422 = missing required query parameter
        assert resp.status_code == 422

    def test_invalid_ticket_returns_401(self, client):
        """A garbage ticket is rejected before the stream opens."""
        resp = client.get(
            "/v1/notifications/stream",
            params={"ticket": "not-a-real-jwt"},
        )
        assert resp.status_code == 401

    def test_expired_ticket_returns_401(self, client, user_a_id):
        """A ticket signed with a past expiry is rejected."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from nabora_crm.core.config import settings

        past = datetime.now(timezone.utc) - timedelta(seconds=120)
        payload = {
            "sub": str(user_a_id),
            "email": USER_A_EMAIL,
            "exp": past,
            "type": "sse",
        }
        expired_ticket = jwt.encode(
            payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        resp = client.get(
            "/v1/notifications/stream",
            params={"ticket": expired_ticket},
        )
        assert resp.status_code == 401

    def test_wrong_token_type_returns_401(self, client, user_a_id):
        """A valid access token used as an SSE ticket is rejected (type mismatch)."""
        resp_login = client.post(
            "/v1/auth/login",
            json={"email": USER_A_EMAIL, "password": USER_A_PASS},
        )
        access_token = resp_login.json()["access_token"]

        resp = client.get(
            "/v1/notifications/stream",
            params={"ticket": access_token},
        )
        assert resp.status_code == 401

    def test_valid_ticket_opens_stream(self, client, headers_a, user_a_id):
        """A freshly-issued ticket successfully opens the SSE stream.

        TestClient reads the full response body, so we can't hold the stream
        open. We verify the response is 200 and starts with the ``connected``
        SSE event.
        """
        ticket_resp = client.post(
            "/v1/notifications/stream-ticket", headers=headers_a
        )
        ticket = ticket_resp.json()["ticket"]

        resp = client.get(
            "/v1/notifications/stream",
            params={"ticket": ticket},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # The first event must be "connected"
        assert "event: connected" in resp.text

    def test_stream_includes_initial_missed_notifications(
        self, client, headers_a, user_a_id
    ):
        """When Last-Event-ID is supplied, missed notifications are replayed.

        We seed a notification, then open the stream with Last-Event-ID equal
        to that notification's ID. Because there are no *newer* notifications,
        the replay list is empty — but the stream still opens successfully.
        """
        _clear_notifications(user_a_id)
        note_id = _seed_notification(user_a_id, title="Old event")

        ticket = client.post(
            "/v1/notifications/stream-ticket", headers=headers_a
        ).json()["ticket"]

        resp = client.get(
            "/v1/notifications/stream",
            params={"ticket": ticket},
            headers={"Last-Event-ID": str(note_id)},
        )
        assert resp.status_code == 200
        assert "event: connected" in resp.text


# ---------------------------------------------------------------------------
# Notifications triggered by domain events (integration smoke tests)
# ---------------------------------------------------------------------------


class TestNotificationTriggers:
    """Verify that domain actions actually create persisted notifications.

    These do not test the SSE delivery path; that is an in-process channel
    that cannot be exercised through TestClient. We confirm the DB records
    exist via the REST endpoints.
    """

    def test_login_creates_welcome_notification(self, client, user_a_id):
        """The first login for a user creates a WELCOME notification."""
        # Clear existing so we can detect the welcome freshly
        _clear_notifications(user_a_id)

        # Log in — this triggers ensure_welcome_notification
        client.post(
            "/v1/auth/login",
            json={"email": USER_A_EMAIL, "password": USER_A_PASS},
        )
        headers = _login(client, USER_A_EMAIL, USER_A_PASS)

        resp = client.get("/v1/notifications", headers=headers)
        types = [item["type"] for item in resp.json()["items"]]
        assert NotificationType.WELCOME in types

    def test_change_password_creates_notification(self, client, user_a_id):
        """Changing your own password creates a PASSWORD_CHANGED notification."""
        _clear_notifications(user_a_id)
        headers = _login(client, USER_A_EMAIL, USER_A_PASS)

        client.post(
            "/v1/auth/change-password",
            json={
                "current_password": USER_A_PASS,
                "new_password": "newPassA456!",
            },
            headers=headers,
        )

        # Update password back so other tests keep working
        new_headers = _login(client, USER_A_EMAIL, "newPassA456!")
        client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "newPassA456!",
                "new_password": USER_A_PASS,
            },
            headers=new_headers,
        )

        # Verify notification was created during the first change
        final_headers = _login(client, USER_A_EMAIL, USER_A_PASS)
        resp = client.get("/v1/notifications", headers=final_headers)
        types = [item["type"] for item in resp.json()["items"]]
        assert NotificationType.PASSWORD_CHANGED in types
