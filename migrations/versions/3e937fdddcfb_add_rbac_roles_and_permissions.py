"""add rbac roles and permissions

Revision ID: 3e937fdddcfb
Revises: 64ce901f220d
Create Date: 2026-11-06 17:40:25.068822

Creates roles, permissions, and role_permissions tables with UUID PKs.
Adds role_id FK to users (nullable first, backfilled, then non-null).
Drops the old role enum column.
Seeds default system roles and permissions.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e937fdddcfb'
down_revision: Union[str, None] = '64ce901f220d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Canonical permission names — must match core/permissions.py
PERMISSIONS = [
    "users:read",
    "users:write",
    "users:delete",
    "crm:read",
    "crm:write",
    "crm:delete",
    "roles:read",
    "roles:write",
    "roles:delete",
    "admin:access",
]

# System roles and their default permissions
SYSTEM_ROLES = {
    "admin": PERMISSIONS,  # all permissions
    "nutritionist": ["crm:read", "crm:write"],
    "fitness": ["crm:read", "crm:write"],
}


def upgrade() -> None:
    # --- Create RBAC tables ---
    op.create_table(
        'permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_permissions_name'), 'permissions', ['name'], unique=True)

    op.create_table(
        'roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('permission_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )

    # --- Add role_id column to users (nullable initially for backfill) ---
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('role_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_users_role_id_roles', 'roles', ['role_id'], ['id'],
            ondelete='RESTRICT',
        )

    # --- Seed permissions ---
    conn = op.get_bind()
    for perm_name in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, name) VALUES (:id, :name) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "name": perm_name},
        )

    # --- Seed system roles and assign permissions ---
    for role_name, perm_names in SYSTEM_ROLES.items():
        # Insert role
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, name, is_system) VALUES (:id, :name, true) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "name": role_name},
        )

        # Get role ID
        role_id = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).scalar()

        # Assign permissions
        for perm_name in perm_names:
            perm_id = conn.execute(
                sa.text("SELECT id FROM permissions WHERE name = :name"),
                {"name": perm_name},
            ).scalar()
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_id, "perm_id": perm_id},
            )

    # --- Backfill users.role_id from old role enum column ---
    for role_name in SYSTEM_ROLES:
        role_id = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).scalar()
        conn.execute(
            sa.text("UPDATE users SET role_id = :role_id WHERE role = :role_name"),
            {"role_id": role_id, "role_name": role_name},
        )

    # --- Make role_id non-nullable and drop the old role enum column ---
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('role_id', nullable=False)
        batch_op.drop_column('role')


def downgrade() -> None:
    # Re-add the old role enum column and backfill from role_id
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.Enum('admin', 'nutritionist', 'fitness', name='role'),
                nullable=True,
            )
        )

    # Backfill role from role_id
    conn = op.get_bind()
    for role_name in SYSTEM_ROLES:
        role_id = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).scalar()
        conn.execute(
            sa.text("UPDATE users SET role = :role_name WHERE role_id = :role_id"),
            {"role_name": role_name, "role_id": role_id},
        )

    # Make role non-nullable, drop role_id FK and column
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('role', nullable=False)
        batch_op.drop_constraint('fk_users_role_id_roles', type_='foreignkey')
        batch_op.drop_column('role_id')

    # Drop RBAC tables
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_table('roles')
    op.drop_index(op.f('ix_permissions_name'), table_name='permissions')
    op.drop_table('permissions')
