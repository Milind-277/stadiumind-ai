"""
app/middleware/role_guard.py — Role-based access control decorator.

Uses Flask's signed session cookie (protected by SECRET_KEY).
No JWT, no database — role is stored in session['role'] after selection.
"""

import functools

from flask import jsonify, redirect, request, session, url_for

VALID_ROLES = {"fan", "organizer", "volunteer", "security"}

# API paths contain this segment (e.g. /fan/api/fan/matches)
_API_PATH_SEGMENT = "/api/"


def _is_api_request() -> bool:
    """Return True if the current request is to an API endpoint."""
    return _API_PATH_SEGMENT in request.path


def require_role(*roles: str):
    """
    Decorator that enforces role-based access.

    - Unauthenticated API requests → 403 JSON with ROLE_001
    - Unauthenticated page requests → redirect to landing
    - Wrong-role API requests → 403 JSON with ROLE_002
    - Wrong-role page requests → redirect to landing

    Usage::

        @bp.route("/dashboard")
        @require_role("organizer")
        def dashboard(): ...

        @bp.route("/admin")
        @require_role("organizer", "security")
        def admin(): ...
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            current_role = session.get("role")

            if not current_role:
                if _is_api_request():
                    return (
                        jsonify(
                            {
                                "success": False,
                                "errors": [
                                    {
                                        "code": "ROLE_001",
                                        "message": "No role selected. Please select a role first.",
                                    }
                                ],
                            }
                        ),
                        403,
                    )
                return redirect(url_for("core.landing"))

            if current_role not in roles:
                if _is_api_request():
                    return (
                        jsonify(
                            {
                                "success": False,
                                "errors": [
                                    {
                                        "code": "ROLE_002",
                                        "message": f"Access denied. Required role(s): {', '.join(roles)}.",
                                    }
                                ],
                            }
                        ),
                        403,
                    )
                return redirect(url_for("core.landing"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def get_current_role() -> str:
    """Return the current session role, or empty string if not set."""
    return session.get("role", "")
