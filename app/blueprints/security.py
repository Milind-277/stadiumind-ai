"""app/blueprints/security.py — Security command center routes (pages + API)."""
from flask import Blueprint, render_template, request, jsonify

from app.middleware.role_guard import require_role
from app.services.security_service import SecurityService
from app.utils.response import success, error
from app.utils.validators import sanitize_string, require_fields
from app.config import Config

bp = Blueprint("security", __name__, url_prefix="/security")
_svc = SecurityService(Config.DATA_DIR)

DEMO_VENUE_ID = "v001"


# ── Page Routes ────────────────────────────────────────────────────────────────

@bp.route("/")
@require_role("security")
def index():
    incidents = _svc.get_all_incidents()
    active = [i for i in incidents if i["is_active"]]
    return render_template("security/command.html", incidents=incidents, active_count=len(active))


@bp.route("/incidents")
@require_role("security")
def incidents():
    all_incidents = _svc.get_all_incidents()
    return render_template("security/incidents.html", incidents=all_incidents)


# ── API Routes ─────────────────────────────────────────────────────────────────

@bp.route("/api/security/incidents")
@require_role("security")
def api_incidents():
    venue_id = request.args.get("venue_id")
    incidents = _svc.get_all_incidents(venue_id)
    active = [i for i in incidents if i["is_active"]]
    return jsonify(success(data={
        "incidents": incidents,
        "total": len(incidents),
        "active": len(active),
    }))


@bp.route("/api/security/incidents", methods=["POST"])
@require_role("security")
def api_log_incident():
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "venue_id", "zone_id", "zone_name", "description")
    if missing:
        return jsonify(*error(f"Field '{missing}' is required.", "VAL_001"))
    result = _svc.log_incident(
        venue_id=sanitize_string(body["venue_id"], 10),
        zone_id=sanitize_string(body["zone_id"], 20),
        zone_name=sanitize_string(body["zone_name"], 100),
        description=sanitize_string(body["description"], 1000),
        reported_by="security",
    )
    return jsonify(success(data=result)), 201


@bp.route("/api/security/incidents/<incident_id>", methods=["PATCH"])
@require_role("security")
def api_update_incident(incident_id: str):
    body = request.get_json(silent=True) or {}
    allowed_fields = {"status", "assigned_to", "notes"}
    update_data = {k: sanitize_string(str(v), 200) for k, v in body.items() if k in allowed_fields}
    if not update_data:
        return jsonify(*error("No valid fields to update.", "VAL_001"))
    result = _svc.update_incident(incident_id, update_data)
    if not result:
        return jsonify(*error("Incident not found.", "DATA_001", status_code=404))
    return jsonify(success(data=result))


@bp.route("/api/security/incidents/<incident_id>/classify", methods=["POST"])
@require_role("security")
def api_classify_incident(incident_id: str):
    result = _svc.classify_incident(incident_id)
    if "error" in result:
        return jsonify(*error(result["error"], "DATA_001", status_code=404))
    return jsonify(success(data=result, ai_powered=True, fallback_used=result.get("fallback_used", False)))


@bp.route("/api/security/zones/heatmap")
@require_role("security")
def api_heatmap():
    venue_id = sanitize_string(request.args.get("venue_id", DEMO_VENUE_ID), max_length=10)
    result = _svc.get_zone_heatmap(venue_id)
    if "error" in result:
        return jsonify(*error(result["error"], "DATA_001", status_code=404))
    return jsonify(success(data=result))


@bp.route("/api/security/protocols/<incident_type>")
@require_role("security")
def api_protocol(incident_type: str):
    incident_type = sanitize_string(incident_type, max_length=50).lower()
    protocol = _svc.get_protocol(incident_type)
    return jsonify(success(data={"incident_type": incident_type, "protocol": protocol}))
