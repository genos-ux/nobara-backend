import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from nabora_crm.admin.views import create_admin
from nabora_crm.api.v1.router import api_router
from nabora_crm.core.config import settings
from nabora_crm.core.exceptions import (
    AdminPrivilegeRequiredError,
    AuthenticationError,
    DomainError,
    EmailSendError,
    InactiveUserError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    PermissionDeniedError,
    UploadError,
)
from nabora_crm.core.logging import setup_logging
from nabora_crm.db.init_db import init_db
from nabora_crm.db.session import engine

setup_logging()
logger = logging.getLogger("nabora_crm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Test database connection on startup
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to PostgreSQL database!")
    except Exception as exc:
        logger.error("Failed to connect to the database: %s", exc)
        raise

    # Create tables and seed admin account
    init_db()

    yield


app = FastAPI(
    title="Nabora CRM API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Domain exception handlers
# ---------------------------------------------------------------------------
# Services and dependencies raise domain exceptions (no HTTP awareness).
# These handlers map each domain exception to the appropriate HTTP response,
# keeping the HTTP layer in main.py where it belongs.

_WWW_AUTH = {"WWW-Authenticate": "Bearer"}


@app.exception_handler(AuthenticationError)
async def handle_authentication_error(_: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
        headers=_WWW_AUTH,
    )


@app.exception_handler(InvalidTokenError)
async def handle_invalid_token_error(_: Request, exc: InvalidTokenError):
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
        headers=_WWW_AUTH,
    )


@app.exception_handler(InvalidRefreshTokenError)
async def handle_invalid_refresh_token_error(_: Request, exc: InvalidRefreshTokenError):
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
    )


@app.exception_handler(InactiveUserError)
async def handle_inactive_user_error(_: Request, exc: InactiveUserError):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)},
    )


@app.exception_handler(AdminPrivilegeRequiredError)
async def handle_admin_privilege_required_error(_: Request, exc: AdminPrivilegeRequiredError):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)},
    )


@app.exception_handler(PermissionDeniedError)
async def handle_permission_denied_error(_: Request, exc: PermissionDeniedError):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)},
    )


@app.exception_handler(EmailSendError)
async def handle_email_send_error(_: Request, exc: EmailSendError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(UploadError)
async def handle_upload_error(_: Request, exc: UploadError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, exc: DomainError):
    """Catch-all for any future domain exceptions not explicitly handled above."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )

# Session middleware for sqladmin authentication
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/v1")

# SQLAdmin dashboard
templates_dir = str(Path(__file__).parent / "admin" / "templates")
create_admin(app, templates_dir)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to Nabora CRM API",
        "status": "success",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }
