"""app/blueprints/organizer.py — Organizer dashboard routes (pages + API)."""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.middleware.role_guard import require_role
from app.services.organizer_service import OrganizerService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("organizer", __name__, url_prefix="/organizer")
_svc = OrganizerService(Config.DATA_DIR)

# Default venue used when no venue_id is provided by the client
DEFAULT_VENUE_ID = "v001"


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role("organizer")
def index():
    """Organizer dashboard — aggregated operations summary."""
    summary = _svc.get_dashboard_summary()
    return render_template("organizer/dashboard.html", summary=summary)


@bp.route("/crowd")
@require_role("organizer")
def crowd():
    """Live crowd monitoring page."""
    return render_template("organizer/crowd.html")


@bp.route("/reports")
@require_role("organizer")
def reports():
    """AI-generated event report page."""
    return render_template("organizer/reports.html")


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/organizer/dashboard")
@require_role("organizer")
def api_dashboard():
    """Return aggregated dashboard summary for all venues."""
    summary = _svc.get_dashboard_summary()
    return jsonify(success(data=summary))


@bp.route("/api/organizer/crowd/live")
@require_role("organizer")
def api_crowd_live():
    """Return live crowd data with simulated real-time jitter."""
    venue_id = request.args.get("venue_id")
    data = _svc.get_live_crowd(venue_id)
    return jsonify(success(data=data))


@bp.route("/api/organizer/crowd/analysis")
@require_role("organizer")
def api_crowd_analysis():
    """Return AI-powered crowd analysis for a venue."""
    venue_id = sanitize_string(
        request.args.get("venue_id", DEFAULT_VENUE_ID), max_length=10
    )
    result = _svc.get_ai_crowd_analysis(venue_id)
    if "error" in result:
        body, status = error(result["error"], "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(
        success(
            data=result,
            ai_powered=True,
            fallback_used=result.get("fallback_used", False),
        )
    )


@bp.route("/api/organizer/reports/generate", methods=["POST"])
@require_role("organizer")
def api_generate_report():
    """Generate an AI operational briefing for a venue."""
    body = request.get_json(silent=True) or {}
    venue_id = sanitize_string(body.get("venue_id", DEFAULT_VENUE_ID), max_length=10)
    result = _svc.generate_event_briefing(venue_id)
    if "error" in result:
        err_body, status = error(result["error"], "DATA_001", status_code=404)
        return jsonify(err_body), status
    return jsonify(
        success(
            data=result,
            ai_powered=True,
            fallback_used=result.get("fallback_used", False),
        )
    )


@bp.route("/api/organizer/alerts/broadcast", methods=["POST"])
@require_role("organizer")
def api_broadcast_alert():
    """Broadcast a venue-wide alert to all systems."""
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "title", "message", "priority", "venue_id")
    if missing:
        err_body, status = error(f"Field '{missing}' is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.broadcast_alert(
        title=sanitize_string(body["title"], 100),
        message=sanitize_string(body["message"], 500),
        priority=sanitize_string(body["priority"], 20),
        venue_id=sanitize_string(body["venue_id"], 10),
    )
    return jsonify(success(data=result))


@bp.route("/api/organizer/incidents")
@require_role("organizer")
def api_incidents():
    """Return all incidents sorted by severity."""
    incidents = _svc.get_all_incidents()
    return jsonify(success(data={"incidents": incidents, "total": len(incidents)}))
