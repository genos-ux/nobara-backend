"""make post topic an enum

Revision ID: e3f4a5b6c7d8
Revises: d2f3a4b5c6d7
Create Date: 2026-11-15 00:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TOPIC_VALUES = (
    'Nutrition Basics',
    'Health & Wellness',
    'Supplement Education',
    'Ingredients Explained',
    'Public Health Topics',
)

POST_TOPIC_ENUM = sa.Enum(*TOPIC_VALUES, name='post_topic')


def upgrade() -> None:
    bind = op.get_bind()

    # Map legacy free-text topics to a valid enum value before enforcing it.
    allowed = ", ".join(f"'{value}'" for value in TOPIC_VALUES)
    op.execute(
        f"UPDATE posts SET topic = 'Nutrition Basics' "
        f"WHERE topic NOT IN ({allowed})"
    )

    if bind.dialect.name == 'postgresql':
        POST_TOPIC_ENUM.create(bind, checkfirst=True)
        op.alter_column(
            'posts',
            'topic',
            existing_type=sa.String(),
            type_=POST_TOPIC_ENUM,
            existing_nullable=False,
            postgresql_using='topic::text::post_topic',
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == 'postgresql':
        op.alter_column(
            'posts',
            'topic',
            existing_type=POST_TOPIC_ENUM,
            type_=sa.String(),
            existing_nullable=False,
            postgresql_using='topic::text',
        )
        POST_TOPIC_ENUM.drop(bind, checkfirst=True)
