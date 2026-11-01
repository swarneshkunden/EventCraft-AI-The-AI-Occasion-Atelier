"""Small, dependency-free helpers shared by planning services."""

from datetime import date
from typing import Any


def enum_value(value: Any) -> Any:
    """Return an enum's primitive value or the original value."""
    return value.value if hasattr(value, "value") else value


def parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO date, returning None when the value is missing or invalid."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
