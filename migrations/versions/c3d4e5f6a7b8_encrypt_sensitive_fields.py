"""encrypt sensitive fields at rest

Revision ID: c3d4e5f6a7b8
Revises: a9b8c7d6e5f4
Create Date: 2026-11-21 00:00:00.000000

Encrypts existing plaintext values in place and widens the columns that used
to be VARCHAR(255) so ciphertext cannot be truncated.

The migration requires ENCRYPTION_KEY to be set. Losing that key makes the
encrypted data unrecoverable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from nabora_crm.core.encryption import (
    decrypt,
    decrypt_deterministic,
    encrypt,
    encrypt_deterministic,
)


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FERNET_PREFIX = "enc:v1:"
_SIV_PREFIX = "siv:v1:"

# (table, column) pairs encrypted with randomized Fernet.
_RANDOM_COLUMNS = [
    ("users", "full_name"),
    ("persons", "name"),
    ("activities", "staff_name"),
    ("activities", "subject"),
    ("activities", "description"),
    ("audit_logs", "actor_email"),
    ("audit_logs", "detail"),
    ("audit_logs", "ip_address"),
    ("notifications", "title"),
    ("notifications", "message"),
]

# (table, column) pairs encrypted deterministically so equality lookups and
# unique indexes keep working.
_DETERMINISTIC_COLUMNS = [
    ("users", "email"),
    ("persons", "email"),
]

# Columns that must be widened before storing ciphertext on PostgreSQL.
_WIDEN_COLUMNS = [
    ("users", "full_name"),
    ("persons", "name"),
    ("activities", "staff_name"),
    ("activities", "subject"),
    ("audit_logs", "actor_email"),
    ("audit_logs", "ip_address"),
    ("notifications", "title"),
]

# Original column types restored on downgrade.
_RESTORE_TYPES = {
    ("users", "full_name"): sa.String(),
    ("persons", "name"): sa.String(),
    ("activities", "staff_name"): sa.String(),
    ("activities", "subject"): sa.String(length=255),
    ("audit_logs", "actor_email"): sa.String(length=255),
    ("audit_logs", "ip_address"): sa.String(length=45),
    ("notifications", "title"): sa.String(length=255),
}


def _widen_columns() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite does not enforce VARCHAR lengths and cannot ALTER COLUMN type.
        return
    for table, column in _WIDEN_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Text(),
            existing_nullable=True,
        )


def _restore_column_types() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for (table, column), target_type in _RESTORE_TYPES.items():
        op.alter_column(
            table,
            column,
            existing_type=sa.Text(),
            type_=target_type,
            existing_nullable=True,
        )


def _transform_column(table: str, column: str, transform) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT id, {column} FROM {table}")).fetchall()
    for row_id, value in rows:
        if value is None:
            continue
        new_value = transform(value)
        if new_value == value:
            continue
        bind.execute(
            sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
            {"value": new_value, "id": row_id},
        )


def _plain_back(value: str | None, transform, prefix: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith(prefix):
        return value
    return transform(value)


def upgrade() -> None:
    _widen_columns()

    for table, column in _RANDOM_COLUMNS:
        _transform_column(table, column, encrypt)

    for table, column in _DETERMINISTIC_COLUMNS:
        _transform_column(table, column, encrypt_deterministic)


def downgrade() -> None:
    for table, column in _DETERMINISTIC_COLUMNS:
        _transform_column(
            table,
            column,
            lambda value: _plain_back(value, decrypt_deterministic, _SIV_PREFIX),
        )

    for table, column in _RANDOM_COLUMNS:
        _transform_column(
            table,
            column,
            lambda value: _plain_back(value, decrypt, _FERNET_PREFIX),
        )

    _restore_column_types()
