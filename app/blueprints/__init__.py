"""app/blueprints/__init__.py"""

from .core import bp as core_bp
from .fan import bp as fan_bp
from .organizer import bp as organizer_bp
from .security import bp as security_bp
from .volunteer import bp as volunteer_bp

__all__ = ["core_bp", "fan_bp", "organizer_bp", "volunteer_bp", "security_bp"]
