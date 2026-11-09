"""add full_name to users

Revision ID: a7c1e9b2d4f6
Revises: 9f1c2d3e4a5b
Create Date: 2026-11-09 12:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c1e9b2d4f6'
down_revision: Union[str, None] = '9f1c2d3e4a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'full_name')
