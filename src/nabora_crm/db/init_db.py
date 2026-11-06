import logging

from nabora_crm.core.config import settings
from nabora_crm.core.permissions import ALL_PERMISSIONS, ADMIN_ACCESS
from nabora_crm.core.security import hash_password
from nabora_crm.db.base import Base
from nabora_crm.db.session import SessionLocal, engine
from nabora_crm.modules.roles.models import Permission, Role
from nabora_crm.modules.users.models import User
from nabora_crm.modules.users.repository import get_user_by_email

logger = logging.getLogger("nabora_crm")

# Default role -> permission mapping for system roles.
DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": ALL_PERMISSIONS,
    "nutritionist": frozenset({"crm:read", "crm:write"}),
    "fitness": frozenset({"crm:read", "crm:write"}),
}

# Human-readable descriptions for system roles.
SYSTEM_ROLE_DESCRIPTIONS: dict[str, str] = {
    "admin": "Full system access",
    "nutritionist": "Nutritionist — CRM read and write",
    "fitness": "Fitness coach — CRM read and write",
}


def _seed_permissions(db) -> None:
    """Create all canonical permissions if they don't exist."""
    existing = {p.name for p in db.query(Permission).all()}
    for perm_name in ALL_PERMISSIONS:
        if perm_name not in existing:
            db.add(Permission(name=perm_name))
    db.commit()


def _seed_roles(db) -> None:
    """Create system roles and assign their default permissions."""
    all_perms = {p.name: p for p in db.query(Permission).all()}

    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(
                name=role_name,
                description=SYSTEM_ROLE_DESCRIPTIONS.get(role_name),
                is_system=True,
            )
            db.add(role)
            db.commit()
            db.refresh(role)
            logger.info("Seeded system role: %s", role_name)

        # Ensure system roles have their default permissions
        current_perm_names = {p.name for p in role.permissions}
        missing = perm_names - current_perm_names
        if missing:
            role.permissions = [
                all_perms[name] for name in (perm_names | current_perm_names)
                if name in all_perms
            ]
            db.commit()


def _seed_admin_user(db) -> None:
    """Create the admin account if it doesn't already exist."""
    existing = get_user_by_email(db, settings.ADMIN_EMAIL)
    if not existing:
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role is None:
            logger.error("Admin role not found — cannot seed admin user")
            raise RuntimeError("Admin role must exist before seeding admin user")

        user = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info("Seeded admin user: %s", user.email)
    else:
        logger.info("Admin user already exists, skipping seed.")


def seed_rbac() -> None:
    """Seed permissions, system roles, and role-permission assignments."""
    db = SessionLocal()
    try:
        _seed_permissions(db)
        _seed_roles(db)
    except Exception as exc:
        db.rollback()
        logger.error("Error seeding RBAC: %s", exc)
        raise
    finally:
        db.close()


def seed_admin_user() -> None:
    """Create the admin account if it doesn't already exist."""
    db = SessionLocal()
    try:
        _seed_admin_user(db)
    except Exception as exc:
        db.rollback()
        logger.error("Error seeding admin user: %s", exc)
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables, seed RBAC data, and seed the admin account."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")
    seed_rbac()
    seed_admin_user()
