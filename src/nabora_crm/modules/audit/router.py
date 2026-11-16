import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import AUDIT_READ
from nabora_crm.db.session import get_db
from nabora_crm.modules.audit.repository import count_audit_logs, list_audit_logs
from nabora_crm.modules.audit.schemas import AuditLogOut, PaginatedAuditLogs
from nabora_crm.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=PaginatedAuditLogs)
def get_audit_logs(
    actor_id: uuid.UUID | None = Query(None, description="Filter by actor user ID"),
    action: str | None = Query(None, description="Filter by action string (e.g. 'post.published')"),
    resource_type: str | None = Query(None, description="Filter by resource type (e.g. 'post', 'user')"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    since: datetime | None = Query(None, description="Only entries at or after this timestamp (ISO 8601)"),
    until: datetime | None = Query(None, description="Only entries at or before this timestamp (ISO 8601)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(AUDIT_READ)),
) -> PaginatedAuditLogs:
    """Return paginated audit log entries, newest first.

    Requires the ``audit:read`` permission (admin only by default).
    All query parameters are optional and can be combined freely.
    """
    entries = list_audit_logs(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        since=since,
        until=until,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    total = count_audit_logs(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        since=since,
        until=until,
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedAuditLogs(
        items=[AuditLogOut.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
