"""app/utils/validators.py — Input sanitisation and validation helpers."""
import html
import re
from typing import Any, Optional


def sanitize_string(value: Any, max_length: int = 500) -> str:
    """Strip, HTML-escape, and truncate a string value."""
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    value = value.strip()
    value = html.escape(value)
    return value[:max_length]


def is_valid_id(value: str) -> bool:
    """Validate a simple alphanumeric ID (letters, digits, underscores, hyphens)."""
    return bool(re.match(r'^[a-zA-Z0-9_\-]{1,64}$', value))


def require_fields(data: dict, *fields: str) -> Optional[str]:
    """Return a field name if any required field is missing or empty, else None."""
    for field in fields:
        if not data.get(field):
            return field
    return None


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp an integer within a range."""
    return max(min_val, min(value, max_val))
