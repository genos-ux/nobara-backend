"""replace rejected post status with unpublished

Revision ID: b8d2f4a6c1e3
Revises: a7c1e9b2d4f6
Create Date: 2026-11-09 13:20:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8d2f4a6c1e3'
down_revision: Union[str, None] = 'a7c1e9b2d4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('ALTER TYPE post_status RENAME TO post_status_old')
        op.execute(
            "CREATE TYPE post_status AS ENUM "
            "('draft', 'pending_review', 'published', 'unpublished')"
        )
        op.execute(
            'ALTER TABLE posts ALTER COLUMN status TYPE post_status USING '
            "(CASE WHEN status::text = 'rejected' THEN 'unpublished' "
            'ELSE status::text END)::post_status'
        )
        op.execute('DROP TYPE post_status_old')
    else:
        op.execute(
            "UPDATE posts SET status = 'unpublished' WHERE status = 'rejected'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('ALTER TYPE post_status RENAME TO post_status_old')
        op.execute(
            "CREATE TYPE post_status AS ENUM "
            "('draft', 'pending_review', 'published', 'rejected')"
        )
        op.execute(
            'ALTER TABLE posts ALTER COLUMN status TYPE post_status USING '
            "(CASE WHEN status::text = 'unpublished' THEN 'rejected' "
            'ELSE status::text END)::post_status'
        )
        op.execute('DROP TYPE post_status_old')
    else:
        op.execute(
            "UPDATE posts SET status = 'rejected' WHERE status = 'unpublished'"
        )
