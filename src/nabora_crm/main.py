import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from nabora_crm.admin.views import create_admin
from nabora_crm.core.config import settings
from nabora_crm.core.logging import setup_logging
from nabora_crm.db.init_db import init_db
from nabora_crm.db.session import engine
from nabora_crm.modules.auth.router import router as auth_router

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

app.include_router(auth_router)

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
