"""add invitation_token_version to users

Revision ID: d2f3a4b5c6d7
Revises: c1e2d3f4a5b6
Create Date: 2026-11-15 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f3a4b5c6d7'
down_revision: Union[str, None] = 'c1e2d3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'invitation_token_version',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'invitation_token_version')
