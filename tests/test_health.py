"""Tests for endpoints, route registration, OpenAPI, RBAC, and domain exceptions.

These tests verify that the refactored application starts correctly,
all routes are registered, RBAC seeding works, and the OpenAPI schema is generated.
"""

import importlib

from nabora_crm.db.base import Base


class TestHealth:
    """Basic health-check tests."""

    def test_root(self, client):
        """Root endpoint returns welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Welcome to Nabora CRM API"
        assert data["status"] == "success"

    def test_health(self, client):
        """Health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestOpenAPI:
    """Verify OpenAPI schema generation."""

    def test_openapi_schema_generated(self, client):
        """OpenAPI schema is available and contains expected info."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Nabora CRM API"
        assert schema["info"]["version"] == "0.1.0"

    def test_auth_routes_in_schema(self, client):
        """All auth endpoints are registered in the OpenAPI schema under /v1."""
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/v1/auth/login" in paths
        assert "/v1/auth/logout" in paths
        assert "/v1/auth/refresh" in paths
        assert "/v1/auth/me" in paths
        assert "/v1/auth/change-password" in paths

    def test_roles_routes_in_schema(self, client):
        """All roles endpoints are registered in the OpenAPI schema under /v1."""
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/v1/roles" in paths
        assert "/v1/roles/permissions" in paths


class TestImports:
    """Verify all module imports resolve without errors."""

    def test_import_main(self):
        """Main module imports successfully."""
        importlib.reload(importlib.import_module("nabora_crm.main"))

    def test_import_core_config(self):
        """Core config imports and settings are loaded."""
        from nabora_crm.core.config import settings
        assert settings.DATABASE_URL is not None

    def test_import_core_security(self):
        """Core security module imports and functions exist."""
        from nabora_crm.core.security import (
            hash_password,
            verify_password,
            create_access_token,
            decode_access_token,
        )
        assert callable(hash_password)
        assert callable(verify_password)
        assert callable(create_access_token)
        assert callable(decode_access_token)

    def test_import_users_repository(self):
        """Users repository imports and functions exist."""
        from nabora_crm.modules.users.repository import get_user_by_email, create_user
        assert callable(get_user_by_email)
        assert callable(create_user)

    def test_import_auth_router(self):
        """Auth router imports and has correct prefix."""
        from nabora_crm.modules.auth.router import router
        assert router.prefix == "/auth"

    def test_import_admin_views(self):
        """Admin views import and create_admin is callable."""
        from nabora_crm.admin.views import create_admin
        assert callable(create_admin)

    def test_import_roles_router(self):
        """Roles router imports and has correct prefix."""
        from nabora_crm.modules.roles.router import router
        assert router.prefix == "/roles"

    def test_import_permissions(self):
        """Core permissions module imports with expected constants."""
        from nabora_crm.core.permissions import ALL_PERMISSIONS, ADMIN_ACCESS
        assert ADMIN_ACCESS in ALL_PERMISSIONS
        assert len(ALL_PERMISSIONS) == 15


class TestDatabase:
    """Verify database models are registered."""

    def test_models_registered(self):
        """All expected tables are registered with Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        assert "users" in table_names
        assert "persons" in table_names
        assert "activities" in table_names
        assert "roles" in table_names
        assert "permissions" in table_names
        assert "role_permissions" in table_names
        assert "posts" in table_names
        assert "notifications" in table_names


class TestDomainExceptions:
    """Verify domain exceptions are mapped to correct HTTP responses."""

    def test_bad_login_returns_401(self, client):
        """AuthenticationError maps to 401 with WWW-Authenticate header."""
        response = client.post(
            "/v1/auth/login",
            json={"email": "nobody@test.test", "password": "wrong"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_missing_token_returns_401(self, client):
        """No bearer token returns 401."""
        response = client.get("/v1/auth/me")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """InvalidTokenError maps to 401."""
        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"

    def test_invalid_refresh_token_returns_401(self, client):
        """InvalidRefreshTokenError maps to 401."""
        response = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired refresh token"

    def test_domain_exceptions_importable(self):
        """All domain exception classes can be imported."""
        from nabora_crm.core.exceptions import (
            AdminPrivilegeRequiredError,
            AuthenticationError,
            DomainError,
            InactiveUserError,
            InvalidRefreshTokenError,
            InvalidTokenError,
            PermissionDeniedError,
        )
        assert issubclass(AuthenticationError, DomainError)
        assert issubclass(InactiveUserError, DomainError)
        assert issubclass(InvalidTokenError, DomainError)
        assert issubclass(InvalidRefreshTokenError, DomainError)
        assert issubclass(AdminPrivilegeRequiredError, DomainError)
        assert issubclass(PermissionDeniedError, DomainError)


class TestRBAC:
    """Verify RBAC seeding, roles API, and permission-based access control."""

    def test_admin_login_works(self, client):
        """The seeded admin user can log in."""
        response = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_admin_profile_has_permissions(self, client):
        """The /me endpoint returns the admin's role and permissions."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert "admin:access" in data["permissions"]
        assert "roles:read" in data["permissions"]
        assert "roles:write" in data["permissions"]

    def test_roles_list_requires_auth(self, client):
        """Unauthenticated requests to /v1/roles return 401."""
        response = client.get("/v1/roles")
        assert response.status_code == 401

    def test_admin_can_list_roles(self, client):
        """Admin user can list all roles."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.get(
            "/v1/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        roles = response.json()
        role_names = [r["name"] for r in roles]
        assert "admin" in role_names
        assert "contributor" in role_names

    def test_admin_can_list_permissions(self, client):
        """Admin user can list all permissions."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.get(
            "/v1/roles/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        perms = response.json()
        perm_names = [p["name"] for p in perms]
        assert "admin:access" in perm_names
        assert "users:read" in perm_names
        assert "crm:read" in perm_names

    def test_admin_can_create_role(self, client):
        """Admin user can create a new role with permissions."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.post(
            "/v1/roles",
            json={
                "name": "manager",
                "description": "CRM manager",
                "permission_names": ["crm:read", "crm:write", "crm:delete"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "manager"
        assert data["is_system"] is False
        perm_names = [p["name"] for p in data["permissions"]]
        assert "crm:read" in perm_names
        assert "crm:write" in perm_names
        assert "crm:delete" in perm_names

    def test_admin_cannot_delete_system_role(self, client):
        """System roles cannot be deleted."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        # Get the admin role's ID
        roles = client.get(
            "/v1/roles",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        admin_role = [r for r in roles if r["name"] == "admin"][0]

        response = client.delete(
            f"/v1/roles/{admin_role['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "System roles cannot be deleted" in response.json()["detail"]

    def test_duplicate_role_name_rejected(self, client):
        """Creating a role with an existing name returns 400."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.post(
            "/v1/roles",
            json={"name": "admin", "permission_names": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_invalid_permission_name_rejected(self, client):
        """Creating a role with a non-existent permission returns 400."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        response = client.post(
            "/v1/roles",
            json={"name": "badrole", "permission_names": ["nonexistent:perm"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]


class TestUserManagement:
    """Verify user management endpoints with permission-based access control."""

    def _admin_headers(self, client):
        """Login as admin and return auth headers."""
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@test.example", "password": "testpass123"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _create_test_user(self, client, email="testuser@example.com"):
        """Create a contributor user via DB and return its ID."""
        from nabora_crm.db.session import SessionLocal
        from nabora_crm.modules.users.models import User
        from nabora_crm.modules.roles.models import Role
        from nabora_crm.core.security import hash_password

        db = SessionLocal()
        try:
            # Delete any existing user with this email (from previous tests)
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                db.delete(existing)
                db.commit()

            role = db.query(Role).filter(Role.name == "contributor").first()
            user = User(
                email=email,
                hashed_password=hash_password("testpass123"),
                role_id=role.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return str(user.id)
        finally:
            db.close()

    def _role_id(self, client, headers, name):
        """Return a role ID by name via the roles API."""
        resp = client.get("/v1/roles", headers=headers)
        assert resp.status_code == 200, resp.text
        for role in resp.json():
            if role["name"] == name:
                return role["id"]
        raise AssertionError(f"{name} role not found")

    def test_admin_can_update_user_role(self, client):
        """Admin can change a user's role."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="role-change@example.com")
        admin_role_id = self._role_id(client, headers, "admin")

        response = client.patch(
            f"/v1/users/{user_id}",
            json={"role_id": admin_role_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "admin"

        fetched = client.get(f"/v1/users/{user_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["role"] == "admin"

    def test_update_user_invalid_role(self, client):
        """Changing to a non-existent role is rejected."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="bad-role@example.com")
        fake_role_id = "00000000-0000-0000-0000-000000000000"

        response = client.patch(
            f"/v1/users/{user_id}",
            json={"role_id": fake_role_id},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Role with id" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    def test_admin_can_get_user(self, client):
        """Admin can fetch a user by ID."""
        headers = self._admin_headers(client)
        me = client.get("/v1/auth/me", headers=headers).json()
        user_id = me["id"]

        response = client.get(f"/v1/users/{user_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.example"
        assert data["role"] == "admin"
        assert data["is_active"] is True

    def test_admin_can_update_user_details(self, client):
        """Admin can update a user's name and email."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="update-me@example.com")

        response = client.patch(
            f"/v1/users/{user_id}",
            json={
                "full_name": "Updated Person",
                "email": "updated@example.com",
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["full_name"] == "Updated Person"
        assert data["email"] == "updated@example.com"

        fetched = client.get(f"/v1/users/{user_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["full_name"] == "Updated Person"
        assert fetched.json()["email"] == "updated@example.com"

    def test_update_user_email_conflict_rejected(self, client):
        """Updating to an email already in use is rejected."""
        headers = self._admin_headers(client)
        first_id = self._create_test_user(client, email="first@example.com")
        self._create_test_user(client, email="second@example.com")

        response = client.patch(
            f"/v1/users/{first_id}",
            json={"email": "second@example.com"},
            headers=headers,
        )
        assert response.status_code == 400
        assert "already exists in the system" in response.json()["detail"]

    def test_update_user_requires_at_least_one_field(self, client):
        """An empty update payload is rejected."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="empty-update@example.com")

        response = client.patch(
            f"/v1/users/{user_id}",
            json={},
            headers=headers,
        )
        assert response.status_code == 422

    def test_update_nonexistent_user(self, client):
        """Updating a non-existent user returns 400."""
        headers = self._admin_headers(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        response = client.patch(
            f"/v1/users/{fake_id}",
            json={"full_name": "Nobody"},
            headers=headers,
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_deactivate_user(self, client):
        """Admin can deactivate a user."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="deactivate@example.com")

        response = client.patch(f"/v1/users/{user_id}/deactivate", headers=headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_reactivate_user(self, client):
        """Admin can reactivate a deactivated user."""
        headers = self._admin_headers(client)
        user_id = self._create_test_user(client, email="reactivate@example.com")

        # Deactivate first
        client.patch(f"/v1/users/{user_id}/deactivate", headers=headers)

        # Then reactivate
        response = client.patch(f"/v1/users/{user_id}/activate", headers=headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_get_nonexistent_user(self, client):
        """Getting a non-existent user returns 400."""
        headers = self._admin_headers(client)
        fake_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/v1/users/{fake_id}", headers=headers)
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_users_endpoints_require_auth(self, client):
        """Unauthenticated requests to users endpoints return 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        assert client.get(f"/v1/users/{fake_id}").status_code == 401
        assert client.get("/v1/users").status_code == 401
        assert client.patch(f"/v1/users/{fake_id}", json={"full_name": "x"}).status_code == 401
        assert client.patch(f"/v1/users/{fake_id}/deactivate").status_code == 401
        assert client.patch(f"/v1/users/{fake_id}/activate").status_code == 401


class TestChangePassword:
    """Verify the current user's change-password endpoint."""

    def _create_user(self, email, password):
        from nabora_crm.db.session import SessionLocal
        from nabora_crm.modules.users.models import User
        from nabora_crm.modules.roles.models import Role
        from nabora_crm.core.security import hash_password

        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                db.delete(existing)
                db.commit()
            role = db.query(Role).filter(Role.name == "contributor").first()
            user = User(
                email=email,
                hashed_password=hash_password(password),
                role_id=role.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return str(user.id)
        finally:
            db.close()

    def _login(self, client, email, password):
        return client.post(
            "/v1/auth/login", json={"email": email, "password": password}
        )

    def _headers(self, client, email, password):
        login = self._login(client, email, password)
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_change_password_success(self, client):
        """A user can change their password with the correct current one."""
        email = "change-pw@test.example"
        self._create_user(email, "oldpassword123")
        headers = self._headers(client, email, "oldpassword123")

        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "oldpassword123",
                "new_password": "newpassword456",
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["message"] == "Password updated successfully"

        assert self._login(client, email, "newpassword456").status_code == 200
        assert self._login(client, email, "oldpassword123").status_code == 401

    def test_change_password_wrong_current(self, client):
        """An incorrect current password is rejected."""
        email = "change-pw-wrong@test.example"
        self._create_user(email, "oldpassword123")
        headers = self._headers(client, email, "oldpassword123")

        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "notmypassword",
                "new_password": "newpassword456",
            },
            headers=headers,
        )
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

        assert self._login(client, email, "oldpassword123").status_code == 200

    def test_change_password_same_password_rejected(self, client):
        """The new password must differ from the current one."""
        email = "change-pw-same@test.example"
        self._create_user(email, "oldpassword123")
        headers = self._headers(client, email, "oldpassword123")

        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "oldpassword123",
                "new_password": "oldpassword123",
            },
            headers=headers,
        )
        assert response.status_code == 422

    def test_change_password_too_short(self, client):
        """The new password must be at least 8 characters."""
        email = "change-pw-short@test.example"
        self._create_user(email, "oldpassword123")
        headers = self._headers(client, email, "oldpassword123")

        response = client.post(
            "/v1/auth/change-password",
            json={"current_password": "oldpassword123", "new_password": "short"},
            headers=headers,
        )
        assert response.status_code == 422

    def test_change_password_requires_auth(self, client):
        """Unauthenticated requests are rejected."""
        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "oldpassword123",
                "new_password": "newpassword456",
            },
        )
        assert response.status_code == 401
