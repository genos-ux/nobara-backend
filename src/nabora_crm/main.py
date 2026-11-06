import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from sqlalchemy import text

from nabora_crm.database import engine
from nabora_crm.models import Base

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

    # Create all database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")

    yield


app = FastAPI(
    title="Nabora CRM API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to Nabora CRM API",
        "status": "success",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }
