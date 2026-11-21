"""store name fields in plaintext

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-21 01:00:00.000000

Decrypts the three name columns so names are stored in plaintext again.
Emails, message content, audit details, and notification text remain encrypted.

Requires ENCRYPTION_KEY so existing ciphertext can be decrypted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from nabora_crm.core.encryption import decrypt, encrypt


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FERNET_PREFIX = "enc:v1:"

# (table, column) pairs that are now stored in plaintext.
_NAME_COLUMNS = [
    ("users", "full_name"),
    ("persons", "name"),
    ("activities", "staff_name"),
]


def _widen_columns() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column in _NAME_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(),
            type_=sa.Text(),
            existing_nullable=True,
        )


def _narrow_columns() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column in _NAME_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Text(),
            type_=sa.String(),
            existing_nullable=True,
        )


def _transform_names(transform) -> None:
    bind = op.get_bind()
    for table, column in _NAME_COLUMNS:
        rows = bind.execute(
            sa.text(f"SELECT id, {column} FROM {table}")
        ).fetchall()
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


def _decrypt_name(value: str) -> str:
    if not isinstance(value, str) or not value.startswith(_FERNET_PREFIX):
        return value
    return decrypt(value)


def upgrade() -> None:
    _transform_names(_decrypt_name)
    _narrow_columns()


def downgrade() -> None:
    _widen_columns()
    _transform_names(encrypt)
