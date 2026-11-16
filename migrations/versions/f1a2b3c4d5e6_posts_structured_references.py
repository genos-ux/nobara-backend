"""posts: replace sources_references with structured JSON + link_for_readers

Revision ID: f1a2b3c4d5e6
Revises: e3f4a5b6c7d8
Create Date: 2026-11-16 18:07:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Add the new structured columns.
    if bind.dialect.name == "postgresql":
        op.add_column("posts", sa.Column("sources_and_references", postgresql.JSONB(), nullable=True))
    else:
        op.add_column("posts", sa.Column("sources_and_references", sa.JSON(), nullable=True))

    op.add_column("posts", sa.Column("link_for_readers", sa.String(), nullable=True))

    # Drop the old free-text column.
    op.drop_column("posts", "sources_references")


def downgrade() -> None:
    # Restore the old text column (data is lost; acceptable for rollback).
    op.add_column("posts", sa.Column("sources_references", sa.Text(), nullable=True))

    op.drop_column("posts", "link_for_readers")
    op.drop_column("posts", "sources_and_references")