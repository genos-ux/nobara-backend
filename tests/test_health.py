"""Tests for basic endpoint health and route registration.

These tests verify that the refactored application starts correctly,
all routes are registered, and the OpenAPI schema is generated.
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


class TestDatabase:
    """Verify database models are registered."""

    def test_models_registered(self):
        """All expected tables are registered with Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        assert "users" in table_names
        assert "persons" in table_names
        assert "activities" in table_names


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
        )
        assert issubclass(AuthenticationError, DomainError)
        assert issubclass(InactiveUserError, DomainError)
        assert issubclass(InvalidTokenError, DomainError)
        assert issubclass(InvalidRefreshTokenError, DomainError)
        assert issubclass(AdminPrivilegeRequiredError, DomainError)
