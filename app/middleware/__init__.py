"""app/middleware/__init__.py"""
from .role_guard import require_role, get_current_role, VALID_ROLES
from .error_handler import register_error_handlers
from .request_logger import register_request_logger

__all__ = [
    "require_role",
    "get_current_role",
    "VALID_ROLES",
    "register_error_handlers",
    "register_request_logger",
]
