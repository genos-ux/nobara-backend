import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import USERS_READ, USERS_WRITE
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.users.schemas import (
    PaginatedUsers,
    UserListItem,
    UserOut,
    UserPostOut,
    UserUpdate,
)
from nabora_crm.modules.users.service import (
    get_user_or_404,
    list_users,
    set_user_active,
    update_user_details,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedUsers)
def get_users(
    search: str | None = Query(None, description="Search by name or email"),
    role_id: uuid.UUID | None = Query(None, description="Filter by role ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_READ)),
) -> PaginatedUsers:
    """List all users with their details, posts, and account status."""
    results, total = list_users(
        db,
        search=search,
        role_id=role_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    items = [
        UserListItem(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
            is_pending=user.is_pending,
            is_email_pending=user.is_email_pending,
            post_count=len(posts),
            posts=[
                UserPostOut(
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
    return PaginatedUsers(
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
        is_email_pending=user.is_email_pending,
    )


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Update a user's personal details and role."""
    user = get_user_or_404(db, user_id)
    user = update_user_details(
        db,
        user,
        full_name=payload.full_name,
        email=str(payload.email) if payload.email is not None else None,
        role_id=payload.role_id,
        actor=_user,
    )
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        is_email_pending=user.is_email_pending,
    )


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Deactivate a user account. The user can no longer authenticate."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=False, actor=_user)
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        is_email_pending=user.is_email_pending,
    )


@router.patch("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(USERS_WRITE)),
) -> UserOut:
    """Reactivate a previously deactivated user account."""
    user = get_user_or_404(db, user_id)
    user = set_user_active(db, user, is_active=True, actor=_user)
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        is_email_pending=user.is_email_pending,
    )
