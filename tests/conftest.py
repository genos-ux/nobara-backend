import os

# Set test environment variables BEFORE importing the app.
# SQLite file-based DB avoids requiring a running PostgreSQL instance.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("REFRESH_SECRET_KEY", "test-refresh-secret-for-testing-only")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.example")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
os.environ.setdefault("CORS_ORIGINS", "")
# Email settings — not actually sent in tests; service is mocked.
os.environ.setdefault("SMTP_HOST", "smtp.test.example")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USERNAME", "test@test.example")
os.environ.setdefault("SMTP_PASSWORD", "testpass")
os.environ.setdefault("SMTP_USE_TLS", "True")
os.environ.setdefault("EMAIL_FROM", "noreply@test.example")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("INVITATION_TOKEN_EXPIRE_DAYS", "7")

import pytest
from fastapi.testclient import TestClient

from nabora_crm.db.base import Base
from nabora_crm.db.session import engine
from nabora_crm.main import app

# Ensure all models are registered with Base.metadata
import nabora_crm.modules.users.models  # noqa: F401
import nabora_crm.modules.crm.models  # noqa: F401
import nabora_crm.modules.roles.models  # noqa: F401


@pytest.fixture(scope="session")
def client():
    """Create a TestClient with a SQLite test database.

    The app lifespan seeds RBAC data (permissions, roles, admin user) on startup.
    """
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db_file():
    """Remove the SQLite test database file after all tests finish."""
    yield
    if os.path.exists("./test.db"):
        os.remove("./test.db")
