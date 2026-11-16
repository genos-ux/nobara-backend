"""add audit_logs table

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-11-16 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "audit_logs" not in inspector.get_table_names():
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("actor_id", sa.Uuid(), nullable=True),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=True),
            sa.Column("resource_id", sa.String(length=255), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["actor_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_id "
        "ON audit_logs (actor_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action "
        "ON audit_logs (action)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at "
        "ON audit_logs (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_action_created "
        "ON audit_logs (actor_id, action, created_at)"
    )

    # Seed audit:read permission if it doesn't exist yet, then assign to admin
    op.execute(
        """
        INSERT INTO permissions (id, name)
        SELECT gen_random_uuid(), 'audit:read'
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions WHERE name = 'audit:read'
        )
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'admin'
          AND p.name = 'audit:read'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "audit_logs" in inspector.get_table_names():
        op.drop_index("ix_audit_logs_actor_action_created", table_name="audit_logs")
        op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
        op.drop_table("audit_logs")

    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id = (
            SELECT id FROM permissions WHERE name = 'audit:read'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE name = 'audit:read'")
