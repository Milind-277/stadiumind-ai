"""app/utils/datetime_utils.py — Date/time formatting helpers."""

from datetime import datetime, timezone


def utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def format_match_time(iso_string: str) -> str:
    """Format an ISO datetime string for display (e.g. 'Jun 17, 2026 — 20:00 UTC')."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y — %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_string


def time_until(iso_string: str) -> str:
    """Return a human-readable 'in X hours' / 'X days ago' string."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = dt - now
        seconds = int(delta.total_seconds())
        if seconds < 0:
            seconds = abs(seconds)
            if seconds < 3600:
                return f"{seconds // 60} minutes ago"
            if seconds < 86400:
                return f"{seconds // 3600} hours ago"
            return f"{seconds // 86400} days ago"
        if seconds < 3600:
            return f"in {seconds // 60} minutes"
        if seconds < 86400:
            return f"in {seconds // 3600} hours"
        return f"in {seconds // 86400} days"
    except (ValueError, AttributeError):
        return ""
