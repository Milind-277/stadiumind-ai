"""
app/blueprints/organizer.py — Organizer dashboard routes (page views + JSON API).

Organizer Features exposed here:
    * **AI Resource Allocation** — decision support embedded in crowd analysis
    * **Incident Monitoring**    — ``GET  /api/organizer/incidents``
    * **Venue Analytics**        — ``GET  /api/organizer/crowd/live``
    * **Match Dashboard**        — ``GET  /api/organizer/dashboard``
    * **AI Recommendations**     — ``POST /api/organizer/reports/generate``

Alert management:
    * **Emergency Alerts**       — ``POST /api/organizer/alerts/broadcast``

All routes are protected by :func:`~app.middleware.role_guard.require_role`
and delegate business logic exclusively to
:class:`~app.services.organizer_service.OrganizerService`.
"""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.constants import DEFAULT_VENUE_ID, ROLE_ORGANIZER
from app.middleware.role_guard import require_role
from app.services.organizer_service import OrganizerService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("organizer", __name__, url_prefix="/organizer")
_svc = OrganizerService(Config.DATA_DIR)


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role(ROLE_ORGANIZER)
def index():
    """Organizer dashboard — aggregated operations and KPI summary.

    Renders a high-level view of active incidents, volunteer availability,
    live match count, and per-venue occupancy to support real-time oversight.
    """
    summary = _svc.get_dashboard_summary()
    return render_template("organizer/dashboard.html", summary=summary)


@bp.route("/crowd")
@require_role(ROLE_ORGANIZER)
def crowd():
    """Live crowd monitoring page — real-time zone density visualisation."""
    return render_template("organizer/crowd.html")


@bp.route("/reports")
@require_role(ROLE_ORGANIZER)
def reports():
    """AI-generated event report page — operational briefings per venue."""
    return render_template("organizer/reports.html")


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/organizer/dashboard")
@require_role(ROLE_ORGANIZER)
def api_dashboard():
    """Return aggregated Match Dashboard summary for all venues.

    Includes: active incident counts, volunteer availability, live match
    count, per-venue occupancy, and crowd alert indicators.

    Returns:
        JSON envelope with the full dashboard summary dict.
    """
    summary = _svc.get_dashboard_summary()
    return jsonify(success(data=summary))


@bp.route("/api/organizer/crowd/live")
@require_role(ROLE_ORGANIZER)
def api_crowd_live():
    """Return live Venue Analytics crowd data with simulated real-time jitter.

    Query parameters:
        venue_id (str): Optional venue filter; omit to get all venues.

    Returns:
        JSON envelope with a ``venues`` list, each containing zone-level
        occupancy, bottleneck flags, and a simulated live attendance count.
    """
    venue_id = request.args.get("venue_id")
    data = _svc.get_live_crowd(venue_id)
    return jsonify(success(data=data))


@bp.route("/api/organizer/crowd/analysis")
@require_role(ROLE_ORGANIZER)
def api_crowd_analysis():
    """Return AI Resource Allocation crowd analysis for a specific venue.

    Query parameters:
        venue_id (str): Target venue (default: ``v001``).

    Returns:
        JSON envelope with AI analysis summary, severity, critical zones,
        recommendations, and Decision Engine decision support payload.
    """
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
@require_role(ROLE_ORGANIZER)
def api_generate_report():
    """Generate an AI Recommendations operational briefing for a venue.

    Request body (JSON):
        venue_id (str): Target venue (default: ``v001``).

    Returns:
        JSON envelope with the full AI briefing including title, summary,
        key points, priorities, and action items.
    """
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
@require_role(ROLE_ORGANIZER)
def api_broadcast_alert():
    """Broadcast a venue-wide Emergency Alert to all stakeholder systems.

    Request body (JSON):
        title (str):    Alert headline (required, max 100 chars).
        message (str):  Alert body text (required, max 500 chars).
        priority (str): Alert priority level (required, max 20 chars).
        venue_id (str): Target venue identifier (required, max 10 chars).

    Returns:
        JSON envelope containing the created alert record and broadcast flag.
    """
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
@require_role(ROLE_ORGANIZER)
def api_incidents():
    """Return all Incident Monitoring data sorted by severity.

    Returns:
        JSON envelope with the full incident list and a ``total`` count,
        sorted critical-first for operational triage.
    """
    incidents = _svc.get_all_incidents()
    return jsonify(success(data={"incidents": incidents, "total": len(incidents)}))
