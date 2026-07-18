"""
app/__init__.py — Flask Application Factory.

Creates and configures the Flask application instance.  Registers all
blueprints, middleware, error handlers, and security headers in a single,
well-ordered factory function so that the application is trivially testable
and free of module-level side effects.
"""

import logging
import os

from flask import Flask

from app.config import Config
from app.constants import CSP_VALUE, LOG_DATE_FORMAT, LOG_FORMAT


def create_app(config_class: type = Config) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_class: A configuration class (default :class:`Config`).
            Pass :class:`TestConfig` in the test suite for isolation.

    Returns:
        A fully-configured :class:`flask.Flask` instance.
    """
    config_class.validate()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # ── Configuration ──────────────────────────────────────────────────────────
    app.secret_key = config_class.SECRET_KEY
    app.config["DEBUG"] = config_class.DEBUG
    app.config["TESTING"] = config_class.TESTING
    app.config["MOCK_AI"] = config_class.MOCK_AI
    app.config["SESSION_COOKIE_HTTPONLY"] = config_class.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config_class.SESSION_COOKIE_SAMESITE

    # ── Logging ────────────────────────────────────────────────────────────────
    _configure_logging(config_class)

    # ── Security Headers ───────────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        """Attach security headers to every outgoing response."""
        for header, value in config_class.SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["Content-Security-Policy"] = CSP_VALUE
        return response

    # ── Register Blueprints ────────────────────────────────────────────────────
    from app.blueprints import (  # noqa: PLC0415
        core_bp,
        fan_bp,
        organizer_bp,
        security_bp,
        volunteer_bp,
    )

    app.register_blueprint(core_bp)
    app.register_blueprint(fan_bp)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(volunteer_bp)
    app.register_blueprint(security_bp)

    # ── Register Middleware ────────────────────────────────────────────────────
    from app.middleware.error_handler import register_error_handlers  # noqa: PLC0415
    from app.middleware.request_logger import register_request_logger  # noqa: PLC0415

    register_error_handlers(app)
    register_request_logger(app)

    # ── Jinja2 Global Helpers ──────────────────────────────────────────────────
    from app.utils.datetime_utils import format_match_time, time_until  # noqa: PLC0415

    app.jinja_env.globals.update(
        format_match_time=format_match_time,
        time_until=time_until,
    )

    logger = logging.getLogger(__name__)
    logger.info(
        "StadiumMind AI application started (debug=%s, mock_ai=%s)",
        config_class.DEBUG,
        config_class.MOCK_AI,
    )

    return app


def _configure_logging(config_class: type) -> None:
    """Configure structured logging for the application.

    Args:
        config_class: The active configuration class, used to read
            ``LOG_LEVEL``, ``LOG_TO_FILE``, and ``LOG_FILE`` settings.
    """
    level = getattr(logging, config_class.LOG_LEVEL.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if config_class.LOG_TO_FILE:
        os.makedirs(os.path.dirname(config_class.LOG_FILE), exist_ok=True)
        handlers.append(logging.FileHandler(config_class.LOG_FILE))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers,
    )
