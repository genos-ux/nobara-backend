"""add subject to activities

Revision ID: a9b8c7d6e5f4
Revises: c2d3e4f5a6b7
Create Date: 2026-11-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    activity_columns = {column['name'] for column in inspector.get_columns('activities')}
    if 'subject' not in activity_columns:
        op.add_column(
            'activities',
            sa.Column('subject', sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    activity_columns = {column['name'] for column in inspector.get_columns('activities')}
    if 'subject' in activity_columns:
        op.drop_column('activities', 'subject')
