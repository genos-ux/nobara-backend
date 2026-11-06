"""Domain-level exceptions raised by service and dependency layers.

These are intentionally framework-agnostic (no HTTP status codes, no FastAPI imports).
Exception handlers in main.py map each one to the appropriate HTTP response.
"""


class DomainError(Exception):
    """Base class for all domain exceptions."""


class AuthenticationError(DomainError):
    """Raised when credentials are invalid."""


class InactiveUserError(DomainError):
    """Raised when a user account is inactive."""


class InvalidTokenError(DomainError):
    """Raised when a JWT access token is missing, malformed, or invalid."""


class InvalidRefreshTokenError(DomainError):
    """Raised when a refresh token is missing, malformed, or invalid."""


class AdminPrivilegeRequiredError(DomainError):
    """Raised when a non-admin user attempts an admin-only action."""


class PermissionDeniedError(DomainError):
    """Raised when a user lacks a required permission."""
