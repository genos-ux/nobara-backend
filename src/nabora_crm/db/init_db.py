import logging

from nabora_crm.core.config import settings
from nabora_crm.core.security import hash_password
from nabora_crm.db.base import Base
from nabora_crm.db.session import SessionLocal, engine
from nabora_crm.modules.users.models import Role, User
from nabora_crm.modules.users.repository import get_user_by_email

logger = logging.getLogger("nabora_crm")


def seed_admin_user() -> None:
    """Create the admin account if it doesn't already exist."""
    db = SessionLocal()
    try:
        existing = get_user_by_email(db, settings.ADMIN_EMAIL)
        if not existing:
            user = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=Role.admin,
                is_active=True,
            )
            db.add(user)
            db.commit()
            logger.info("Seeded admin user: %s", user.email)
        else:
            logger.info("Admin user already exists, skipping seed.")
    except Exception as exc:
        db.rollback()
        logger.error("Error seeding admin user: %s", exc)
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables and seed the admin account."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")
    seed_admin_user()
