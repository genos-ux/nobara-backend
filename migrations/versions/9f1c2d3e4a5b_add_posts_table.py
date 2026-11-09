"""add posts table

Revision ID: 9f1c2d3e4a5b
Revises: 4b0fd6f770eb
Create Date: 2026-11-09 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f1c2d3e4a5b'
down_revision: Union[str, None] = '4b0fd6f770eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'posts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('headline', sa.String(), nullable=True),
        sa.Column('introduction', sa.Text(), nullable=True),
        sa.Column('evidence_explanation', sa.Text(), nullable=True),
        sa.Column('practical_guidance', sa.Text(), nullable=False),
        sa.Column('sources_references', sa.Text(), nullable=True),
        sa.Column(
            'section',
            sa.Enum('nutrition', 'fitness', name='post_section'),
            nullable=False,
        ),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('placeholder_color', sa.String(length=7), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'draft', 'pending_review', 'published', 'rejected',
                name='post_status',
            ),
            nullable=False,
        ),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_posts_section'), 'posts', ['section'], unique=False)
    op.create_index(op.f('ix_posts_topic'), 'posts', ['topic'], unique=False)
    op.create_index(op.f('ix_posts_status'), 'posts', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_posts_status'), table_name='posts')
    op.drop_index(op.f('ix_posts_topic'), table_name='posts')
    op.drop_index(op.f('ix_posts_section'), table_name='posts')
    op.drop_table('posts')

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='post_status').drop(bind, checkfirst=True)
        sa.Enum(name='post_section').drop(bind, checkfirst=True)
