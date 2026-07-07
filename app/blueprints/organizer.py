"""app/blueprints/organizer.py — Organizer dashboard routes (pages + API)."""
from flask import Blueprint, render_template, request, jsonify

from app.middleware.role_guard import require_role
from app.services.organizer_service import OrganizerService
from app.utils.response import success, error
from app.utils.validators import sanitize_string, require_fields
from app.config import Config

bp = Blueprint("organizer", __name__, url_prefix="/organizer")
_svc = OrganizerService(Config.DATA_DIR)


# ── Page Routes ────────────────────────────────────────────────────────────────

@bp.route("/")
@require_role("organizer")
def index():
    summary = _svc.get_dashboard_summary()
    return render_template("organizer/dashboard.html", summary=summary)


@bp.route("/crowd")
@require_role("organizer")
def crowd():
    return render_template("organizer/crowd.html")


@bp.route("/reports")
@require_role("organizer")
def reports():
    return render_template("organizer/reports.html")


# ── API Routes ─────────────────────────────────────────────────────────────────

@bp.route("/api/organizer/dashboard")
@require_role("organizer")
def api_dashboard():
    summary = _svc.get_dashboard_summary()
    return jsonify(success(data=summary))


@bp.route("/api/organizer/crowd/live")
@require_role("organizer")
def api_crowd_live():
    venue_id = request.args.get("venue_id")
    data = _svc.get_live_crowd(venue_id)
    return jsonify(success(data=data))


@bp.route("/api/organizer/crowd/analysis")
@require_role("organizer")
def api_crowd_analysis():
    venue_id = sanitize_string(request.args.get("venue_id", "v001"), max_length=10)
    result = _svc.get_ai_crowd_analysis(venue_id)
    if "error" in result:
        return jsonify(*error(result["error"], "DATA_001", status_code=404))
    return jsonify(success(data=result, ai_powered=True, fallback_used=result.get("fallback_used", False)))


@bp.route("/api/organizer/reports/generate", methods=["POST"])
@require_role("organizer")
def api_generate_report():
    body = request.get_json(silent=True) or {}
    venue_id = sanitize_string(body.get("venue_id", "v001"), max_length=10)
    result = _svc.generate_event_briefing(venue_id)
    if "error" in result:
        return jsonify(*error(result["error"], "DATA_001", status_code=404))
    return jsonify(success(data=result, ai_powered=True, fallback_used=result.get("fallback_used", False)))


@bp.route("/api/organizer/alerts/broadcast", methods=["POST"])
@require_role("organizer")
def api_broadcast_alert():
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "title", "message", "priority", "venue_id")
    if missing:
        return jsonify(*error(f"Field '{missing}' is required.", "VAL_001"))
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
    incidents = _svc.get_all_incidents()
    return jsonify(success(data={"incidents": incidents, "total": len(incidents)}))
