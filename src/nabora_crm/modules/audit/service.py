"""Audit log service.

Provides a single ``log_action`` helper that all other services call after
their main transaction has committed. Failures are swallowed and logged so
that an audit write never breaks a business operation.
"""
import logging
import uuid

from sqlalchemy.orm import Session

from nabora_crm.modules.audit.models import AuditAction  # noqa: F401 — re-exported
from nabora_crm.modules.audit.repository import insert_audit_log

logger = logging.getLogger("nabora_crm")


def log_action(
    db: Session,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Record one audit log entry.

    This is best-effort: any exception is caught, logged, and the session is
    rolled back so the caller's subsequent work is not affected.
    """
    try:
        insert_audit_log(
            db,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )
    except Exception:
        logger.exception("Failed to write audit log entry for action=%s", action)
        db.rollback()
