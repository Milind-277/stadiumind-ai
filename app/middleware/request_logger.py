"""app/middleware/request_logger.py — Structured request logging middleware."""

import logging
import time
import uuid

from flask import Flask, g, request

logger = logging.getLogger(__name__)


def register_request_logger(app: Flask) -> None:
    """Attach before/after request hooks for structured request logging."""

    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.monotonic()

    @app.after_request
    def after_request(response):
        duration_ms = round(
            (time.monotonic() - g.get("start_time", time.monotonic())) * 1000, 1
        )
        # Inject request_id header for debugging
        response.headers["X-Request-ID"] = g.get("request_id", "-")
        logger.info(
            "request",
            extra={
                "request_id": g.get("request_id", "-"),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "role": "session_role",  # avoid importing session here
                "ip": request.remote_addr,
            },
        )
        return response
