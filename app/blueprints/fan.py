"""app/blueprints/fan.py — Fan portal routes (pages + API)."""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.middleware.role_guard import require_role
from app.services.fan_service import FanService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("fan", __name__, url_prefix="/fan")
_svc = FanService(Config.DATA_DIR)

# Default venue used when no venue_id is provided by the client
DEFAULT_VENUE_ID = "v001"


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role("fan")
def index():
    """Fan home page — shows upcoming matches and live match status."""
    matches = _svc.get_all_matches()
    live_match = next((m for m in matches if m["is_live"]), None)
    return render_template("fan/home.html", matches=matches[:4], live_match=live_match)


@bp.route("/schedule")
@require_role("fan")
def schedule():
    """Fan schedule page — full match list."""
    matches = _svc.get_all_matches()
    return render_template("fan/schedule.html", matches=matches)


@bp.route("/wayfinding")
@require_role("fan")
def wayfinding():
    """Fan wayfinding page — venue navigation assistant."""
    venue_id = request.args.get("venue_id", DEFAULT_VENUE_ID)
    return render_template("fan/wayfinding.html", venue_id=venue_id)


@bp.route("/chat")
@require_role("fan")
def chat():
    """Fan AI chat page — real-time assistance."""
    venue_id = request.args.get("venue_id", DEFAULT_VENUE_ID)
    return render_template("fan/chat.html", venue_id=venue_id)


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/fan/matches")
@require_role("fan")
def api_matches():
    """Return all matches with formatted display data."""
    matches = _svc.get_all_matches()
    return jsonify(success(data={"matches": matches}))


@bp.route("/api/fan/matches/<match_id>")
@require_role("fan")
def api_match_detail(match_id: str):
    """Return full detail for a single match by ID."""
    detail = _svc.get_match_detail(match_id)
    if not detail:
        body, status = error("Match not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=detail))


@bp.route("/api/fan/chat", methods=["POST"])
@require_role("fan")
def api_chat():
    """Process a fan chat message through the AI assistant."""
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
@require_role("fan")
def api_wayfinding():
    """Return AI-enhanced wayfinding directions to a venue destination."""
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
@require_role("fan")
def api_venue(venue_id: str):
    """Return venue information including gates, food courts, and accessibility."""
    venue = _svc.get_venue_info(venue_id)
    if not venue:
        body, status = error("Venue not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=venue))
