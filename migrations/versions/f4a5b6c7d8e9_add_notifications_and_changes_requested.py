"""add notifications and changes_requested post status

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-11-15 03:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TYPE post_status ADD VALUE IF NOT EXISTS 'changes_requested'"
        )

    op.add_column(
        'posts',
        sa.Column('review_note', sa.Text(), nullable=True),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=True),
        sa.Column(
            'is_read',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['post_id'], ['posts.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_notifications_user_id'),
        'notifications',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_post_id'),
        'notifications',
        ['post_id'],
        unique=False,
    )
    op.create_index(
        'ix_notifications_user_read_created',
        'notifications',
        ['user_id', 'is_read', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_notifications_user_read_created',
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_post_id'),
        table_name='notifications',
    )
    op.drop_index(
        op.f('ix_notifications_user_id'),
        table_name='notifications',
    )
    op.drop_table('notifications')
    op.drop_column('posts', 'review_note')
    # PostgreSQL cannot remove a single enum value; changes_requested remains
    # in post_status after downgrade but is unused by the previous schema.
