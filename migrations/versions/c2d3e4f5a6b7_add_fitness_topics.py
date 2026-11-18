"""add fitness topics to post_topic enum

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-11-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TOPIC_VALUES = (
    'Nutrition Basics',
    'Health & Wellness',
    'Supplement Education',
    'Ingredients Explained',
    'Public Health Topics',
)

FITNESS_TOPIC_VALUES = (
    'Training',
    'Performance',
    'Recovery',
    'Fitness Education',
)

POST_TOPIC_ENUM_ALL = sa.Enum(
    *OLD_TOPIC_VALUES, *FITNESS_TOPIC_VALUES, name='post_topic'
)
POST_TOPIC_ENUM_OLD = sa.Enum(*OLD_TOPIC_VALUES, name='post_topic')


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    # ALTER TYPE ... ADD VALUE cannot run inside a regular transaction on
    # older PostgreSQL versions, so use an autocommit block.
    with op.get_context().autocommit_block():
        for value in FITNESS_TOPIC_VALUES:
            op.execute(f"ALTER TYPE post_topic ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    allowed = ", ".join(f"'{value}'" for value in FITNESS_TOPIC_VALUES)
    op.execute(
        f"UPDATE posts SET topic = 'Nutrition Basics' "
        f"WHERE topic::text IN ({allowed})"
    )
    op.alter_column(
        'posts',
        'topic',
        existing_type=POST_TOPIC_ENUM_ALL,
        type_=sa.String(),
        existing_nullable=False,
        postgresql_using='topic::text',
    )
    POST_TOPIC_ENUM_ALL.drop(bind, checkfirst=True)
    POST_TOPIC_ENUM_OLD.create(bind, checkfirst=True)
    op.alter_column(
        'posts',
        'topic',
        existing_type=sa.String(),
        type_=POST_TOPIC_ENUM_OLD,
        existing_nullable=False,
        postgresql_using='topic::text::post_topic',
    )
