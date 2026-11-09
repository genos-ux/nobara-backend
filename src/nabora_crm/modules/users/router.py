import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import USERS_READ, USERS_WRITE
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.users.schemas import (
    ContributorOut,
    ContributorPostOut,
    PaginatedContributors,
    UserOut,
)
from nabora_crm.modules.users.service import (
    get_user_or_404,
    list_contributors,
    set_user_active,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/contributors", response_model=PaginatedContributors)
def get_contributors(
    search: str | None = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_READ)),
) -> PaginatedContributors:
    """List contributors with their details, posts, and account status."""
    results, total = list_contributors(
        db,
        search=search,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    items = [
        ContributorOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
            is_pending=user.is_pending,
            post_count=len(posts),
            posts=[
                ContributorPostOut(
                    id=post.id,
                    headline=post.headline,
                    topic=post.topic,
                    section=post.section,
                    status=post.status,
                    updated_at=post.updated_at,
                )
                for post in posts
            ],
        )
        for user, posts in results
    ]
    pages = (total + page_size - 1) // page_size
    return PaginatedContributors(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_READ)),
) -> UserOut:
    """Get a single user by ID."""
    user = get_user_or_404(db, user_id)
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Deactivate a user account. The user can no longer authenticate."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=False)
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )


@router.patch("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Reactivate a previously deactivated user account."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=True)
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
    )
