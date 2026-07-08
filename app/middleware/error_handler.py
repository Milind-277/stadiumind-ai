"""app/middleware/error_handler.py — Global exception → JSON response mapping."""

import logging
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)


def _base_error_body(code: str, message: str) -> dict:
    return {
        "success": False,
        "data": None,
        "meta": {
            "request_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "errors": [{"code": code, "message": message}],
    }


def register_error_handlers(app: Flask) -> None:
    """Register all global error handlers on the Flask app."""

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(_base_error_body("BAD_REQUEST", str(e))), 400

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(_base_error_body("FORBIDDEN", "Access denied.")), 403

    @app.errorhandler(404)
    def not_found(e):
        # Return HTML for page routes, JSON for API routes
        if request.path.startswith("/api/"):
            return jsonify(_base_error_body("NOT_FOUND", "Resource not found.")), 404
        from flask import render_template

        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return (
            jsonify(_base_error_body("METHOD_NOT_ALLOWED", "Method not allowed.")),
            405,
        )

    @app.errorhandler(500)
    def internal_error(e):
        req_id = str(uuid.uuid4())[:8]
        # Log full traceback internally; never expose to client
        logger.error(
            "Unhandled exception",
            extra={"request_id": req_id, "path": request.path},
            exc_info=True,
        )
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    _base_error_body(
                        "INTERNAL_ERROR",
                        f"An unexpected error occurred. Reference: {req_id}",
                    )
                ),
                500,
            )
        from flask import render_template

        return render_template("errors/500.html", request_id=req_id), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        req_id = str(uuid.uuid4())[:8]
        logger.error(
            "Uncaught exception: %s",
            str(e),
            extra={"request_id": req_id},
            exc_info=True,
        )
        if request.path.startswith("/api/"):
            return (
                jsonify(
                    _base_error_body(
                        "INTERNAL_ERROR",
                        f"An unexpected error occurred. Reference: {req_id}",
                    )
                ),
                500,
            )
        from flask import render_template

        return render_template("errors/500.html", request_id=req_id), 500
