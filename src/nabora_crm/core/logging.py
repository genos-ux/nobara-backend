import json
import logging

# Fields whose values must never appear in logs.
_SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "token",
        "refresh_token",
        "access_token",
        "invite_token",
        "hashed_password",
    }
)

_REDACTED = "[REDACTED]"


def redact_credentials(body: bytes) -> dict:
    """Parse a JSON request body and replace sensitive field values with [REDACTED].

    Returns an empty dict if the body is not valid JSON or is empty.
    The original bytes are never modified.
    """
    if not body:
        return {}
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        k: (_REDACTED if k in _SENSITIVE_FIELDS else v)
        for k, v in data.items()
    }


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging.

    Call once at startup (e.g. in the app lifespan or main entry point)
    to ensure consistent log formatting across all modules.
    """
    logging.basicConfig(level=level)
