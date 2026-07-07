"""app/utils/response.py — Standard API response builder."""
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional


def success(
    data: Any = None,
    ai_powered: bool = False,
    from_cache: bool = False,
    fallback_used: bool = False,
) -> dict:
    """Build a successful API response envelope."""
    return {
        "success": True,
        "data": data,
        "meta": {
            "request_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ai_powered": ai_powered,
            "from_cache": from_cache,
            "fallback_used": fallback_used,
        },
        "errors": None,
    }


def error(
    message: str,
    code: str = "ERROR",
    field: Optional[str] = None,
    status_code: int = 400,
) -> tuple:
    """Build an error API response envelope and return (dict, status_code)."""
    err = {"code": code, "message": message}
    if field:
        err["field"] = field
    return (
        {
            "success": False,
            "data": None,
            "meta": {
                "request_id": str(uuid.uuid4())[:8],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "errors": [err],
        },
        status_code,
    )
