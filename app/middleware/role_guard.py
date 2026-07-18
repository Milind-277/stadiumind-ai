"""
app/middleware/role_guard.py — Role-based access control decorator.

Uses Flask's signed session cookie (protected by SECRET_KEY).
No JWT, no database — the role is stored in ``session['role']`` after the
role-selector step on the landing page.

Design:
    * Unauthenticated API requests  → 403 JSON  (code: ROLE_001)
    * Unauthenticated page requests → redirect to landing
    * Wrong-role API requests       → 403 JSON  (code: ROLE_002)
    * Wrong-role page requests      → redirect to landing
"""

import functools
from typing import Callable

from flask import jsonify, redirect, request, session, url_for

from app.constants import ALL_ROLES, SESSION_ROLE_KEY

# Re-export for consumers that import VALID_ROLES directly from this module.
VALID_ROLES = ALL_ROLES

# API paths contain this segment (e.g. /fan/api/fan/matches)
_API_PATH_SEGMENT = "/api/"

# ── Error codes ────────────────────────────────────────────────────────────────
_ERR_NO_ROLE = "ROLE_001"
_ERR_WRONG_ROLE = "ROLE_002"


def _is_api_request() -> bool:
    """Return ``True`` if the current request targets an API endpoint."""
    return _API_PATH_SEGMENT in request.path


def _forbidden_json(code: str, message: str):
    """Return a 403 JSON response for role-guard violations.

    Args:
        code:    Machine-readable error code (e.g. ``"ROLE_001"``).
        message: Human-readable description of the access failure.

    Returns:
        A Flask JSON response with HTTP status 403.
    """
    return (
        jsonify(
            {
                "success": False,
                "errors": [{"code": code, "message": message}],
            }
        ),
        403,
    )


def require_role(*roles: str) -> Callable:
    """Decorator that enforces role-based access control.

    Usage::

        @bp.route("/dashboard")
        @require_role("organizer")
        def dashboard(): ...

        @bp.route("/admin")
        @require_role("organizer", "security")
        def admin(): ...

    Args:
        *roles: One or more role strings that are permitted to access the view.

    Returns:
        A decorator that wraps the view function with role enforcement.
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            current_role = session.get(SESSION_ROLE_KEY)

            if not current_role:
                if _is_api_request():
                    return _forbidden_json(
                        _ERR_NO_ROLE,
                        "No role selected. Please select a role first.",
                    )
                return redirect(url_for("core.landing"))

            if current_role not in roles:
                if _is_api_request():
                    return _forbidden_json(
                        _ERR_WRONG_ROLE,
                        f"Access denied. Required role(s): {', '.join(roles)}.",
                    )
                return redirect(url_for("core.landing"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def get_current_role() -> str:
    """Return the active session role, or an empty string if not set.

    Returns:
        The role string (e.g. ``"fan"``) or ``""`` when unauthenticated.
    """
    return session.get(SESSION_ROLE_KEY, "")
