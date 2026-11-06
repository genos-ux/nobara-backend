import logging

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("nabora_crm")


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str

    # JWT settings
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # Admin account
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    # CORS (comma-separated origins)
    CORS_ORIGINS: str = ""


try:
    settings = Settings()  # type: ignore[call-arg]
except ValidationError as exc:
    for error in exc.errors():
        field = error.get("loc", ["unknown"])[0]
        logger.error("Missing required env variable: %s", field)
    raise
