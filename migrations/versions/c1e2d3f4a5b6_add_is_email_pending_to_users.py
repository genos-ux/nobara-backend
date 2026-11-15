"""add is_email_pending to users

Revision ID: c1e2d3f4a5b6
Revises: b8d2f4a6c1e3
Create Date: 2026-11-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1e2d3f4a5b6'
down_revision: Union[str, None] = 'b8d2f4a6c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'is_email_pending',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Backfill: users who have not set a password yet are email-pending.
    op.execute('UPDATE users SET is_email_pending = is_pending')


def downgrade() -> None:
    op.drop_column('users', 'is_email_pending')
