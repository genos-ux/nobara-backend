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

import asyncio
import uuid
from unittest.mock import patch

import pytest

from nabora_crm.core.security import (
    create_invitation_token,
    create_stream_ticket,
    hash_password,
)
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.notifications.broker import NotificationBroker
from nabora_crm.modules.notifications.models import Notification, NotificationType
from nabora_crm.modules.notifications.repository import create_notification
from nabora_crm.modules.notifications.service import notify_user
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
        assert resp.status_code == 401

    def test_unread_count_requires_auth(self, client):
        resp = client.get("/v1/notifications/unread-count")
        assert resp.status_code == 401

    def test_read_all_requires_auth(self, client):
        resp = client.post("/v1/notifications/read-all")
        assert resp.status_code == 401

    def test_stream_ticket_requires_auth(self, client):
        resp = client.post("/v1/notifications/stream-ticket")
        assert resp.status_code == 401

    def test_mark_read_requires_auth(self, client):
        resp = client.patch(f"/v1/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 401


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
        headers_b = _login(client, USER_B_EMAIL, USER_B_PASS)
        count_resp = client.get(
            "/v1/notifications/unread-count", headers=headers_b
        )
        assert count_resp.json()["count"] == 1


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
        """A freshly-issued ticket successfully opens the SSE stream."""
        ticket_resp = client.post(
            "/v1/notifications/stream-ticket", headers=headers_a
        )
        ticket = ticket_resp.json()["ticket"]

        with client.stream(
            "GET",
            "/v1/notifications/stream",
            params={"ticket": ticket},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            assert next(response.iter_lines()) == "event: connected"

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

        with client.stream(
            "GET",
            "/v1/notifications/stream",
            params={"ticket": ticket},
            headers={"Last-Event-ID": str(note_id)},
        ) as response:
            assert response.status_code == 200
            lines = response.iter_lines()
            assert next(lines) == "event: connected"


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


# ---------------------------------------------------------------------------
# Additional domain-event coverage
# ---------------------------------------------------------------------------


def _admin_headers(client) -> dict[str, str]:
    return _login(client, "admin@test.example", "testpass123")


def _notification_items(
    client, headers: dict[str, str], **params
) -> list[dict]:
    query = {"page": 1, "page_size": 100}
    query.update(params)
    response = client.get("/v1/notifications", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _find_notification(
    items: list[dict], notification_type: str, post_id: str | None = None
) -> dict:
    return next(
        item
        for item in items
        if item["type"] == notification_type
        and (post_id is None or item["post_id"] == post_id)
    )


def _post_payload(**overrides) -> dict:
    payload = {
        "headline": "Notification trigger post",
        "practical_guidance": "Eat well.",
        "section": "nutrition",
        "topic": "Nutrition Basics",
    }
    payload.update(overrides)
    return payload


class TestAdditionalNotificationTriggers:
    def test_post_workflow_notifies_reviewers_and_author(self, client):
        admin_headers = _admin_headers(client)
        suffix = uuid.uuid4().hex[:8]
        email = f"notif-post-{suffix}@test.example"
        _get_or_create_user(email, "contribpass123", "Post Notifier")
        contributor_headers = _login(client, email, "contribpass123")

        created = client.post(
            "/v1/posts", json=_post_payload(), headers=contributor_headers
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]

        submitted = client.post(
            f"/v1/posts/{post_id}/submit", headers=contributor_headers
        )
        assert submitted.status_code == 200, submitted.text
        _find_notification(
            _notification_items(client, admin_headers),
            NotificationType.POST_SUBMITTED,
            post_id,
        )

        published = client.post(
            f"/v1/posts/{post_id}/publish", headers=admin_headers
        )
        assert published.status_code == 200, published.text
        _find_notification(
            _notification_items(client, contributor_headers),
            NotificationType.POST_PUBLISHED,
            post_id,
        )

        unpublished = client.post(
            f"/v1/posts/{post_id}/unpublish", headers=admin_headers
        )
        assert unpublished.status_code == 200, unpublished.text
        _find_notification(
            _notification_items(client, contributor_headers),
            NotificationType.POST_UNPUBLISHED,
            post_id,
        )

        edited = client.patch(
            f"/v1/posts/{post_id}",
            json={"headline": "Reviewer edit"},
            headers=admin_headers,
        )
        assert edited.status_code == 200, edited.text
        _find_notification(
            _notification_items(client, contributor_headers),
            NotificationType.POST_UPDATED,
            post_id,
        )

        deleted = client.delete(f"/v1/posts/{post_id}", headers=admin_headers)
        assert deleted.status_code == 204, deleted.text
        _find_notification(
            _notification_items(client, contributor_headers),
            NotificationType.POST_DELETED,
        )

    def test_pending_post_and_changes_requested_notify(self, client):
        admin_headers = _admin_headers(client)
        suffix = uuid.uuid4().hex[:8]
        email = f"notif-changes-{suffix}@test.example"
        _get_or_create_user(email, "contribpass123", "Changes Notifier")
        contributor_headers = _login(client, email, "contribpass123")

        created = client.post(
            "/v1/posts",
            json=_post_payload(status="pending_review"),
            headers=contributor_headers,
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        _find_notification(
            _notification_items(client, admin_headers),
            NotificationType.POST_SUBMITTED,
            post_id,
        )

        requested = client.post(
            f"/v1/posts/{post_id}/request-changes",
            json={"note": "Add references."},
            headers=admin_headers,
        )
        assert requested.status_code == 200, requested.text
        notification = _find_notification(
            _notification_items(client, contributor_headers),
            NotificationType.POST_CHANGES_REQUESTED,
            post_id,
        )
        assert "Add references." in notification["message"]

    def test_role_user_and_account_notifications(self, client):
        admin_headers = _admin_headers(client)
        suffix = uuid.uuid4().hex[:8]
        email = f"notif-user-{suffix}@test.example"
        password = "contribpass123"
        user_id = _get_or_create_user(email, password, "User Notifier")
        headers = _login(client, email, password)

        role_name = f"notification-role-{suffix}"
        created_role = client.post(
            "/v1/roles",
            json={
                "name": role_name,
                "permission_names": ["posts:read", "posts:write"],
            },
            headers=admin_headers,
        )
        assert created_role.status_code == 201, created_role.text
        role_id = created_role.json()["id"]

        assigned = client.patch(
            f"/v1/users/{user_id}",
            json={"role_id": role_id},
            headers=admin_headers,
        )
        assert assigned.status_code == 200, assigned.text
        _find_notification(
            _notification_items(client, headers),
            NotificationType.ROLE_CHANGED,
        )

        updated_role = client.put(
            f"/v1/roles/{role_id}",
            json={"permission_names": ["posts:read"]},
            headers=admin_headers,
        )
        assert updated_role.status_code == 200, updated_role.text
        _find_notification(
            _notification_items(client, headers),
            NotificationType.ROLE_UPDATED,
        )

        renamed = client.patch(
            f"/v1/users/{user_id}",
            json={"full_name": "Renamed User"},
            headers=admin_headers,
        )
        assert renamed.status_code == 200, renamed.text
        _find_notification(
            _notification_items(client, headers),
            NotificationType.USER_UPDATED,
        )

        client.patch(f"/v1/users/{user_id}/deactivate", headers=admin_headers)
        client.patch(f"/v1/users/{user_id}/activate", headers=admin_headers)
        items = _notification_items(client, headers)
        _find_notification(items, NotificationType.USER_DEACTIVATED)
        _find_notification(items, NotificationType.USER_ACTIVATED)

        changed = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": password,
                "new_password": "newcontribpass123",
            },
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        _find_notification(
            _notification_items(client, headers),
            NotificationType.PASSWORD_CHANGED,
        )

    @patch("nabora_crm.modules.invitations.service.send_invitation_email")
    def test_invitation_accept_notifies_admins_and_welcome_user(
        self, mock_send_email, client
    ):
        admin_headers = _admin_headers(client)
        suffix = uuid.uuid4().hex[:8]
        email = f"notif-invite-{suffix}@test.example"

        roles = client.get("/v1/roles", headers=admin_headers).json()
        role_id = next(role["id"] for role in roles if role["name"] == "contributor")

        invited = client.post(
            "/v1/invitations",
            json={
                "full_name": "Invited Notifier",
                "email": email,
                "role_id": role_id,
            },
            headers=admin_headers,
        )
        assert invited.status_code == 201, invited.text

        token = create_invitation_token(
            {"sub": invited.json()["id"], "email": email}
        )
        accepted = client.post(
            "/v1/invitations/accept",
            json={"token": token, "password": "invitepass123"},
        )
        assert accepted.status_code == 200, accepted.text

        _find_notification(
            _notification_items(client, admin_headers),
            NotificationType.INVITATION_ACCEPTED,
        )
        user_headers = _login(client, email, "invitepass123")
        _find_notification(
            _notification_items(client, user_headers),
            NotificationType.WELCOME,
        )

    def test_mark_read_scoped_to_user(self, client, user_a_id, user_b_id):
        _clear_notifications(user_a_id)
        note_id = _seed_notification(user_a_id, title="Scoped notification")
        headers_a = _login(client, USER_A_EMAIL, USER_A_PASS)
        headers_b = _login(client, USER_B_EMAIL, USER_B_PASS)

        forbidden = client.patch(
            f"/v1/notifications/{note_id}/read", headers=headers_b
        )
        assert forbidden.status_code == 404

        marked = client.patch(
            f"/v1/notifications/{note_id}/read", headers=headers_a
        )
        assert marked.status_code == 200, marked.text
        assert marked.json()["is_read"] is True

    def test_notify_user_creates_unread_notification(self, user_a_id):
        _clear_notifications(user_a_id)
        db = SessionLocal()
        try:
            notification = notify_user(
                db,
                user_a_id,
                notification_type="test_event",
                title="Direct notification",
                message="Hello",
            )[0]
            assert notification.user_id == user_a_id
            assert notification.is_read is False
        finally:
            db.close()

    def test_broker_delivers_only_to_subscribed_user(self):
        async def scenario():
            broker = NotificationBroker()
            broker.bind_loop(asyncio.get_running_loop())
            user_id = uuid.uuid4()
            other_id = uuid.uuid4()
            queue = broker.subscribe(user_id)
            other_queue = broker.subscribe(other_id)

            broker.publish(user_id, {"id": "one"})
            assert await asyncio.wait_for(queue.get(), timeout=1) == {"id": "one"}
            assert other_queue.empty()

            broker.unsubscribe(user_id, queue)
            broker.publish(user_id, {"id": "two"})
            assert queue.empty()

        asyncio.run(scenario())
