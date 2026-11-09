import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nabora_crm.core.permissions import (
    POSTS_DELETE,
    POSTS_READ,
    POSTS_REVIEW,
    POSTS_WRITE,
)
from nabora_crm.db.session import get_db
from nabora_crm.modules.auth.dependencies import require_permission
from nabora_crm.modules.posts.models import PostSection, PostStatus
from nabora_crm.modules.posts.schemas import (
    PaginatedPosts,
    PostCreate,
    PostListItem,
    PostOut,
    PostUpdate,
)
from nabora_crm.modules.posts.service import (
    create_post,
    delete_post,
    get_post_or_404,
    list_posts,
    publish_post,
    reject_post,
    submit_for_review,
    update_post,
)
from nabora_crm.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostOut, status_code=201)
def create_post_endpoint(
    payload: PostCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_WRITE)),
) -> PostOut:
    """Create a post as a draft or submit it for review."""
    post = create_post(db, user=user, payload=payload)
    return PostOut.model_validate(post)


@router.get("", response_model=PaginatedPosts)
def list_posts_endpoint(
    section: PostSection | None = None,
    status: PostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_READ)),
) -> PaginatedPosts:
    """List posts visible to the current user, with optional filters."""
    posts, total = list_posts(
        db,
        user=user,
        section=section,
        status=status,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    items = [
        PostListItem(
            id=post.id,
            title=post.headline,
            author=post.author_email,
            topic=post.topic,
            status=post.status,
            updated_at=post.updated_at,
        )
        for post in posts
    ]
    pages = (total + page_size - 1) // page_size
    return PaginatedPosts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{post_id}", response_model=PostOut)
def get_post_endpoint(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_READ)),
) -> PostOut:
    """Get a single post."""
    post = get_post_or_404(db, user=user, post_id=post_id)
    return PostOut.model_validate(post)


@router.patch("/{post_id}", response_model=PostOut)
def update_post_endpoint(
    post_id: uuid.UUID,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_WRITE)),
) -> PostOut:
    """Update a post. Authors can edit their own posts."""
    post = update_post(db, user=user, post_id=post_id, payload=payload)
    return PostOut.model_validate(post)


@router.delete("/{post_id}", status_code=204)
def delete_post_endpoint(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_DELETE)),
) -> None:
    """Delete a post. Authors can delete their own posts."""
    delete_post(db, user=user, post_id=post_id)


@router.post("/{post_id}/submit", response_model=PostOut)
def submit_post_endpoint(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_WRITE)),
) -> PostOut:
    """Submit a draft post for admin review."""
    post = submit_for_review(db, user=user, post_id=post_id)
    return PostOut.model_validate(post)


@router.post("/{post_id}/publish", response_model=PostOut)
def publish_post_endpoint(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_REVIEW)),
) -> PostOut:
    """Publish a post that is pending review (admin only)."""
    post = publish_post(db, user=user, post_id=post_id)
    return PostOut.model_validate(post)


@router.post("/{post_id}/reject", response_model=PostOut)
def reject_post_endpoint(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(POSTS_REVIEW)),
) -> PostOut:
    """Reject a post that is pending review (admin only)."""
    post = reject_post(db, user=user, post_id=post_id)
    return PostOut.model_validate(post)
