"""
app/__init__.py — Flask Application Factory.

Creates and configures the Flask app. Registers all blueprints,
middleware, error handlers, and security headers.
"""
import logging
import os

from flask import Flask

from app.config import Config


def create_app(config_class=Config) -> Flask:
    """Create and configure the Flask application."""

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
        for header, value in config_class.SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        return response

    # ── Register Blueprints ────────────────────────────────────────────────────
    from app.blueprints import core_bp, fan_bp, organizer_bp, volunteer_bp, security_bp
    app.register_blueprint(core_bp)
    app.register_blueprint(fan_bp)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(volunteer_bp)
    app.register_blueprint(security_bp)

    # ── Register Middleware ────────────────────────────────────────────────────
    from app.middleware.error_handler import register_error_handlers
    from app.middleware.request_logger import register_request_logger
    register_error_handlers(app)
    register_request_logger(app)

    # ── Jinja2 Global Helpers ──────────────────────────────────────────────────
    from app.utils.datetime_utils import format_match_time, time_until
    app.jinja_env.globals.update(
        format_match_time=format_match_time,
        time_until=time_until,
    )

    logger = logging.getLogger(__name__)
    logger.info("StadiumMind AI application started (debug=%s, mock_ai=%s)",
                config_class.DEBUG, config_class.MOCK_AI)

    return app


def _configure_logging(config_class: type) -> None:
    """Configure structured logging."""
    level = getattr(logging, config_class.LOG_LEVEL.upper(), logging.INFO)
    handlers = [logging.StreamHandler()]

    if config_class.LOG_TO_FILE:
        os.makedirs(os.path.dirname(config_class.LOG_FILE), exist_ok=True)
        handlers.append(logging.FileHandler(config_class.LOG_FILE))

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
    )
