"""
app/blueprints/fan.py — Fan portal routes (page views + JSON API).

Fan Features exposed here:
    * **AI Match Assistant**  — ``POST /api/fan/chat``
    * **Crowd Prediction**    — crowd data embedded in wayfinding decision support
    * **Route Recommendation**— ``GET  /api/fan/wayfinding``
    * **Stadium Navigation**  — wayfinding page + AI guidance
    * **Emergency Alerts**    — urgent flag surfaced through chat and wayfinding

All routes are protected by :func:`~app.middleware.role_guard.require_role`
and delegate business logic exclusively to :class:`~app.services.fan_service.FanService`.
"""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.constants import DEFAULT_VENUE_ID, ROLE_FAN
from app.middleware.role_guard import require_role
from app.services.fan_service import FanService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("fan", __name__, url_prefix="/fan")
_svc = FanService(Config.DATA_DIR)


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role(ROLE_FAN)
def index():
    """Fan home page — shows live match status and upcoming fixtures.

    Renders the first four matches and highlights any currently live match so
    fans see at-a-glance what is happening in the stadium right now.
    """
    matches = _svc.get_all_matches()
    live_match = next((m for m in matches if m["is_live"]), None)
    return render_template("fan/home.html", matches=matches[:4], live_match=live_match)


@bp.route("/schedule")
@require_role(ROLE_FAN)
def schedule():
    """Fan schedule page — full fixture list with live indicators."""
    matches = _svc.get_all_matches()
    return render_template("fan/schedule.html", matches=matches)


@bp.route("/wayfinding")
@require_role(ROLE_FAN)
def wayfinding():
    """Fan wayfinding page — AI-powered venue navigation assistant."""
    venue_id = request.args.get("venue_id", DEFAULT_VENUE_ID)
    return render_template("fan/wayfinding.html", venue_id=venue_id)


@bp.route("/chat")
@require_role(ROLE_FAN)
def chat():
    """Fan AI chat page — real-time natural language assistance."""
    venue_id = request.args.get("venue_id", DEFAULT_VENUE_ID)
    return render_template("fan/chat.html", venue_id=venue_id)


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/fan/matches")
@require_role(ROLE_FAN)
def api_matches():
    """Return all matches with formatted display data.

    Returns:
        JSON envelope containing a ``matches`` list sorted by kickoff time.
    """
    matches = _svc.get_all_matches()
    return jsonify(success(data={"matches": matches}))


@bp.route("/api/fan/matches/<match_id>")
@require_role(ROLE_FAN)
def api_match_detail(match_id: str):
    """Return full detail for a single match by ID.

    Args:
        match_id: URL path segment identifying the match (e.g. ``"m001"``).

    Returns:
        JSON match detail on success, or a 404 error envelope.
    """
    detail = _svc.get_match_detail(match_id)
    if not detail:
        body, status = error("Match not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=detail))


@bp.route("/api/fan/chat", methods=["POST"])
@require_role(ROLE_FAN)
def api_chat():
    """Process a fan chat message through the AI Match Assistant.

    Request body (JSON):
        message (str): The fan's natural language query (required, max 500 chars).
        venue_id (str): Venue context for the response (optional, default v001).

    Returns:
        JSON envelope with ``reply``, ``suggestions``, ``urgent`` flag, and
        AI metadata (``ai_powered``, ``from_cache``, ``fallback_used``).
    """
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "message")
    if missing:
        err_body, status = error(f"Field '{missing}' is required.", "VAL_001")
        return jsonify(err_body), status
    message = sanitize_string(body.get("message", ""), max_length=500)
    venue_id = sanitize_string(body.get("venue_id", DEFAULT_VENUE_ID), max_length=10)
    result = _svc.chat(message, venue_id)
    return jsonify(
        success(
            data=result,
            ai_powered=result.get("ai_powered", True),
            from_cache=result.get("from_cache", False),
            fallback_used=result.get("fallback_used", False),
        )
    )


@bp.route("/api/fan/wayfinding")
@require_role(ROLE_FAN)
def api_wayfinding():
    """Return AI-enhanced route recommendations to a venue destination.

    Query parameters:
        venue_id (str): Target venue (default: ``v001``).
        to (str):       Destination name within the venue (required).

    Returns:
        JSON envelope with wayfinding guidance, gate recommendations, and
        crowd-avoidance tips powered by the Decision Engine.
    """
    venue_id = sanitize_string(
        request.args.get("venue_id", DEFAULT_VENUE_ID), max_length=10
    )
    destination = sanitize_string(request.args.get("to", ""), max_length=100)
    if not destination:
        err_body, status = error("'to' parameter is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.get_wayfinding(venue_id, destination)
    return jsonify(success(data=result, ai_powered=True))


@bp.route("/api/fan/venue/<venue_id>")
@require_role(ROLE_FAN)
def api_venue(venue_id: str):
    """Return venue information including gates, food courts, and accessibility.

    Args:
        venue_id: URL path segment identifying the venue (e.g. ``"v001"``).

    Returns:
        JSON venue detail on success, or a 404 error envelope.
    """
    venue = _svc.get_venue_info(venue_id)
    if not venue:
        body, status = error("Venue not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=venue))
