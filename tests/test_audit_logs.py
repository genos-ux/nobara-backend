"""Tests for the audit log REST endpoints.

Covers:
- GET /v1/audit-logs  — paginated list with all filter combinations
- Authentication and permission guards (requires audit:read)
- Route registration in the OpenAPI schema
- Domain actions actually produce audit log entries (integration smoke tests)
"""

import uuid

import pytest

from nabora_crm.core.security import hash_password
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.audit.models import AuditAction, AuditLog
from nabora_crm.modules.audit.repository import insert_audit_log
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.users.models import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin@test.example"
ADMIN_PASS = "testpass123"

CONTRIB_EMAIL = "audit_contrib@test.example"
CONTRIB_PASS = "contribPass1!"


def _login(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _get_or_create_contributor(email: str, password: str, full_name: str) -> uuid.UUID:
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


def _seed_log(
    *,
    action: str = AuditAction.LOGIN,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    resource_type: str | None = "user",
    resource_id: str | None = None,
    detail: str = "Test audit entry",
) -> uuid.UUID:
    db = SessionLocal()
    try:
        entry = insert_audit_log(
            db,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
        )
        return entry.id
    finally:
        db.close()


def _clear_logs() -> None:
    db = SessionLocal()
    try:
        db.query(AuditLog).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def admin_headers(client):
    return _login(client, ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def contrib_id():
    return _get_or_create_contributor(CONTRIB_EMAIL, CONTRIB_PASS, "Audit Contrib")


@pytest.fixture(scope="module")
def contrib_headers(client, contrib_id):
    return _login(client, CONTRIB_EMAIL, CONTRIB_PASS)


# ---------------------------------------------------------------------------
# OpenAPI route registration
# ---------------------------------------------------------------------------


class TestAuditRoutes:
    def test_route_in_openapi(self, client):
        schema = client.get("/openapi.json").json()
        assert "/v1/audit-logs" in schema["paths"]


# ---------------------------------------------------------------------------
# Authentication and permission guards
# ---------------------------------------------------------------------------


class TestAuditAuth:
    def test_requires_auth(self, client):
        # No token → 401 (AuthenticationError from the Bearer dependency)
        resp = client.get("/v1/audit-logs")
        assert resp.status_code == 401

    def test_contributor_cannot_access(self, client, contrib_headers):
        resp = client.get("/v1/audit-logs", headers=contrib_headers)
        assert resp.status_code == 403

    def test_admin_can_access(self, client, admin_headers):
        resp = client.get("/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# List audit logs
# ---------------------------------------------------------------------------


class TestListAuditLogs:
    def test_returns_paginated_shape(self, client, admin_headers):
        resp = client.get("/v1/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert "pages" in body

    def test_entry_shape(self, client, admin_headers):
        _clear_logs()
        actor_id = uuid.uuid4()
        _seed_log(
            action=AuditAction.LOGIN,
            actor_id=actor_id,
            actor_email="someone@test.example",
            resource_type="user",
            resource_id=str(actor_id),
            detail="Logged in.",
        )
        resp = client.get("/v1/audit-logs", headers=admin_headers)
        item = resp.json()["items"][0]
        assert "id" in item
        assert "action" in item
        assert "actor_id" in item
        assert "actor_email" in item
        assert "resource_type" in item
        assert "resource_id" in item
        assert "detail" in item
        assert "ip_address" in item
        assert "created_at" in item
        assert item["action"] == AuditAction.LOGIN

    def test_newest_first_ordering(self, client, admin_headers):
        _clear_logs()
        for i in range(3):
            _seed_log(action=AuditAction.LOGIN, detail=f"Entry {i}")
        resp = client.get("/v1/audit-logs", headers=admin_headers)
        timestamps = [item["created_at"] for item in resp.json()["items"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_pagination(self, client, admin_headers):
        _clear_logs()
        for _ in range(5):
            _seed_log(action=AuditAction.LOGIN)
        resp = client.get(
            "/v1/audit-logs", params={"page": 1, "page_size": 2}, headers=admin_headers
        )
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["pages"] == 3

    def test_second_page(self, client, admin_headers):
        _clear_logs()
        for _ in range(5):
            _seed_log(action=AuditAction.LOGIN)
        resp = client.get(
            "/v1/audit-logs", params={"page": 2, "page_size": 2}, headers=admin_headers
        )
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["page"] == 2


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


class TestAuditLogFilters:
    def test_filter_by_action(self, client, admin_headers):
        _clear_logs()
        _seed_log(action=AuditAction.LOGIN)
        _seed_log(action=AuditAction.POST_PUBLISHED)
        resp = client.get(
            "/v1/audit-logs",
            params={"action": AuditAction.LOGIN},
            headers=admin_headers,
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == AuditAction.LOGIN

    def test_filter_by_actor_id(self, client, admin_headers):
        _clear_logs()
        actor_a = uuid.uuid4()
        actor_b = uuid.uuid4()
        _seed_log(action=AuditAction.LOGIN, actor_id=actor_a)
        _seed_log(action=AuditAction.LOGIN, actor_id=actor_b)
        resp = client.get(
            "/v1/audit-logs",
            params={"actor_id": str(actor_a)},
            headers=admin_headers,
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["actor_id"] == str(actor_a)

    def test_filter_by_resource_type(self, client, admin_headers):
        _clear_logs()
        _seed_log(action=AuditAction.POST_CREATED, resource_type="post")
        _seed_log(action=AuditAction.USER_UPDATED, resource_type="user")
        resp = client.get(
            "/v1/audit-logs",
            params={"resource_type": "post"},
            headers=admin_headers,
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["resource_type"] == "post"

    def test_filter_by_resource_id(self, client, admin_headers):
        _clear_logs()
        rid = str(uuid.uuid4())
        _seed_log(action=AuditAction.POST_PUBLISHED, resource_type="post", resource_id=rid)
        _seed_log(action=AuditAction.POST_PUBLISHED, resource_type="post", resource_id=str(uuid.uuid4()))
        resp = client.get(
            "/v1/audit-logs",
            params={"resource_id": rid},
            headers=admin_headers,
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["resource_id"] == rid

    def test_combined_filters(self, client, admin_headers):
        _clear_logs()
        actor = uuid.uuid4()
        _seed_log(action=AuditAction.LOGIN, actor_id=actor, resource_type="user")
        _seed_log(action=AuditAction.POST_CREATED, actor_id=actor, resource_type="post")
        _seed_log(action=AuditAction.LOGIN, resource_type="user")
        resp = client.get(
            "/v1/audit-logs",
            params={"actor_id": str(actor), "action": AuditAction.LOGIN},
            headers=admin_headers,
        )
        assert resp.json()["total"] == 1

    def test_empty_result_when_no_match(self, client, admin_headers):
        _clear_logs()
        _seed_log(action=AuditAction.LOGIN)
        resp = client.get(
            "/v1/audit-logs",
            params={"action": AuditAction.ROLE_DELETED},
            headers=admin_headers,
        )
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []


# ---------------------------------------------------------------------------
# Domain integration — actions produce audit log entries
# ---------------------------------------------------------------------------


class TestAuditTriggers:
    """Verify that real API calls leave audit log entries."""

    def test_login_creates_audit_entry(self, client, admin_headers):
        _clear_logs()
        client.post(
            "/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        )
        fresh_headers = _login(client, ADMIN_EMAIL, ADMIN_PASS)
        resp = client.get(
            "/v1/audit-logs",
            params={"action": AuditAction.LOGIN},
            headers=fresh_headers,
        )
        assert resp.json()["total"] >= 1
        actions = [item["action"] for item in resp.json()["items"]]
        assert AuditAction.LOGIN in actions

    def test_change_password_creates_audit_entry(self, client, contrib_id):
        _clear_logs()
        headers = _login(client, CONTRIB_EMAIL, CONTRIB_PASS)

        client.post(
            "/v1/auth/change-password",
            json={"current_password": CONTRIB_PASS, "new_password": "NewPass999!"},
            headers=headers,
        )
        # Change back so the fixture keeps working
        new_headers = _login(client, CONTRIB_EMAIL, "NewPass999!")
        client.post(
            "/v1/auth/change-password",
            json={"current_password": "NewPass999!", "new_password": CONTRIB_PASS},
            headers=new_headers,
        )

        # Read logs as admin
        admin_headers = _login(client, ADMIN_EMAIL, ADMIN_PASS)
        resp = client.get(
            "/v1/audit-logs",
            params={"action": AuditAction.PASSWORD_CHANGED},
            headers=admin_headers,
        )
        assert resp.json()["total"] >= 1

    def test_role_create_update_delete_creates_audit_entries(self, client, admin_headers):
        _clear_logs()

        # Create
        create_resp = client.post(
            "/v1/roles",
            json={"name": "audit_test_role", "description": "temp", "permission_names": ["posts:read"]},
            headers=admin_headers,
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["id"]

        # Update
        client.put(
            f"/v1/roles/{role_id}",
            json={"name": "audit_test_role", "description": "updated", "permission_names": ["posts:read"]},
            headers=admin_headers,
        )

        # Delete
        client.delete(f"/v1/roles/{role_id}", headers=admin_headers)

        fresh_admin = _login(client, ADMIN_EMAIL, ADMIN_PASS)
        resp = client.get("/v1/audit-logs", headers=fresh_admin)
        actions = {item["action"] for item in resp.json()["items"]}
        assert AuditAction.ROLE_CREATED in actions
        assert AuditAction.ROLE_UPDATED in actions
        assert AuditAction.ROLE_DELETED in actions

    def test_post_lifecycle_creates_audit_entries(self, client, contrib_headers):
        _clear_logs()

        # Create post
        create_resp = client.post(
            "/v1/posts",
            json={
                "practical_guidance": "Audit test content",
                "section": "nutrition",
                "topic": "Nutrition Basics",
                "status": "draft",
            },
            headers=contrib_headers,
        )
        assert create_resp.status_code == 201
        post_id = create_resp.json()["id"]

        # Submit for review
        client.post(f"/v1/posts/{post_id}/submit", headers=contrib_headers)

        # Admin publishes
        admin_h = _login(client, ADMIN_EMAIL, ADMIN_PASS)
        client.post(f"/v1/posts/{post_id}/publish", headers=admin_h)

        # Admin unpublishes
        client.post(f"/v1/posts/{post_id}/unpublish", headers=admin_h)

        # Admin deletes
        client.delete(f"/v1/posts/{post_id}", headers=admin_h)

        resp = client.get("/v1/audit-logs", headers=admin_h)
        actions = {item["action"] for item in resp.json()["items"]}
        assert AuditAction.POST_CREATED in actions
        assert AuditAction.POST_SUBMITTED in actions
        assert AuditAction.POST_PUBLISHED in actions
        assert AuditAction.POST_UNPUBLISHED in actions
        assert AuditAction.POST_DELETED in actions
