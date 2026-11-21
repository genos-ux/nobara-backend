"""Application-level encryption for sensitive database fields.

Values are encrypted before they are written and decrypted when they are read,
so the database (and its backups) only ever contains ciphertext.

Two schemes are used:

* ``EncryptedString`` — Fernet (AES-128-CBC + HMAC, randomized). Used for
  names, message content, audit details, and notification text.
* ``DeterministicEncryptedString`` — AES-SIV (deterministic, authenticated).
  Used for email addresses so equality lookups and unique indexes keep
  working. Identical plaintext values produce identical ciphertext.

The master key comes from the ``ENCRYPTION_KEY`` environment variable and must
be a Fernet key. The AES-SIV key is derived from it with HKDF-SHA256.

Ciphertext is prefixed with a version marker (``enc:v1:`` or ``siv:v1:``) so
values can be identified and future key rotations can be detected.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from nabora_crm.core.config import settings

_FERNET_PREFIX = "enc:v1:"
_SIV_PREFIX = "siv:v1:"
_SIV_INFO = b"nabora-aes-siv-v1"


class EncryptionError(RuntimeError):
    """Raised when data cannot be encrypted or decrypted."""


def _load_keys() -> tuple[Fernet, AESSIV]:
    key = settings.ENCRYPTION_KEY.strip()
    try:
        fernet = Fernet(key.encode())
        raw_key = base64.urlsafe_b64decode(key.encode())
    except Exception as exc:  # noqa: BLE001 - re-raised with a clear message
        raise EncryptionError(
            "ENCRYPTION_KEY is invalid. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from exc

    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=None,
        info=_SIV_INFO,
    ).derive(raw_key)
    return fernet, AESSIV(derived)


_fernet, _aes_siv = _load_keys()


def encrypt(value: str | None) -> str | None:
    """Encrypt a value with Fernet, leaving ``None`` untouched."""
    if value is None:
        return None
    if value.startswith(_FERNET_PREFIX):
        return value
    token = _fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_FERNET_PREFIX}{token}"


def decrypt(value: str | None) -> str | None:
    """Decrypt a Fernet value, leaving ``None`` untouched."""
    if value is None:
        return None
    if not value.startswith(_FERNET_PREFIX):
        raise EncryptionError(
            "Encountered a value that is not encrypted with a known key version"
        )
    try:
        return _fernet.decrypt(value[len(_FERNET_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError(
            "Could not decrypt value: wrong ENCRYPTION_KEY or corrupted data"
        ) from exc


def encrypt_deterministic(value: str | None) -> str | None:
    """Encrypt a value deterministically with AES-SIV."""
    if value is None:
        return None
    if value.startswith(_SIV_PREFIX):
        return value
    token = _aes_siv.encrypt(value.encode("utf-8"), None)
    encoded = base64.urlsafe_b64encode(token).decode("utf-8")
    return f"{_SIV_PREFIX}{encoded}"


def decrypt_deterministic(value: str | None) -> str | None:
    """Decrypt an AES-SIV value, leaving ``None`` untouched."""
    if value is None:
        return None
    if not value.startswith(_SIV_PREFIX):
        raise EncryptionError(
            "Encountered a value that is not deterministically encrypted "
            "with a known key version"
        )
    try:
        token = base64.urlsafe_b64decode(value[len(_SIV_PREFIX):].encode("utf-8"))
        return _aes_siv.decrypt(token, None).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - normalise crypto errors
        raise EncryptionError(
            "Could not decrypt value: wrong ENCRYPTION_KEY or corrupted data"
        ) from exc


class EncryptedString(TypeDecorator[str]):
    """Randomized, authenticated encryption for text columns."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt(value)


class DeterministicEncryptedString(TypeDecorator[str]):
    """Deterministic, authenticated encryption for searchable text columns."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_deterministic(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt_deterministic(value)
