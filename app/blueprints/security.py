"""
app/blueprints/security.py — Security command centre routes (page views + JSON API).

Security Features exposed here:
    * **Threat Detection**        — zone heatmap + bottleneck analysis
    * **Incident Classification** — ``POST /api/security/incidents/<id>/classify``
    * **Risk Analysis**           — AI classification with severity and confidence
    * **Emergency Response**      — ``GET  /api/security/protocols/<type>``
    * **AI Decision Support**     — Decision Engine embedded in every classification

All routes are protected by :func:`~app.middleware.role_guard.require_role`
and delegate business logic exclusively to
:class:`~app.services.security_service.SecurityService`.
"""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.constants import DEFAULT_VENUE_ID, INCIDENT_UPDATE_FIELDS, ROLE_SECURITY
from app.middleware.role_guard import require_role
from app.services.security_service import SecurityService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("security", __name__, url_prefix="/security")
_svc = SecurityService(Config.DATA_DIR)


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role(ROLE_SECURITY)
def index():
    """Security command centre — live Threat Detection incident overview.

    Renders all incidents with active ones highlighted for immediate triage.
    """
    incidents = _svc.get_all_incidents()
    active = [i for i in incidents if i["is_active"]]
    return render_template(
        "security/command.html", incidents=incidents, active_count=len(active)
    )


@bp.route("/incidents")
@require_role(ROLE_SECURITY)
def incidents():
    """Security incident list page — full history with severity and status badges."""
    all_incidents = _svc.get_all_incidents()
    return render_template("security/incidents.html", incidents=all_incidents)


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/security/incidents")
@require_role(ROLE_SECURITY)
def api_incidents():
    """Return all incidents for Incident Classification triage.

    Query parameters:
        venue_id (str): Optional venue filter; omit to get all incidents.

    Returns:
        JSON envelope with ``incidents`` list, ``total`` count, and ``active`` count.
        Incidents are sorted active-first, then by descending severity.
    """
    venue_id = request.args.get("venue_id")
    incidents = _svc.get_all_incidents(venue_id)
    active = [i for i in incidents if i["is_active"]]
    return jsonify(
        success(
            data={
                "incidents": incidents,
                "total": len(incidents),
                "active": len(active),
            }
        )
    )


@bp.route("/api/security/incidents", methods=["POST"])
@require_role(ROLE_SECURITY)
def api_log_incident():
    """Log a new security incident into the Incident Classification workflow.

    Request body (JSON):
        venue_id (str):   Venue where the incident occurred (required).
        zone_id (str):    Zone identifier within the venue (required).
        zone_name (str):  Human-readable zone name (required).
        description (str): Free-text incident description (required).

    Returns:
        JSON envelope with the new incident ID and initial status (HTTP 201).
    """
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "venue_id", "zone_id", "zone_name", "description")
    if missing:
        err_body, status = error(f"Field '{missing}' is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.log_incident(
        venue_id=sanitize_string(body["venue_id"], 10),
        zone_id=sanitize_string(body["zone_id"], 20),
        zone_name=sanitize_string(body["zone_name"], 100),
        description=sanitize_string(body["description"], 1000),
        reported_by=ROLE_SECURITY,
    )
    return jsonify(success(data=result)), 201


@bp.route("/api/security/incidents/<incident_id>", methods=["PATCH"])
@require_role(ROLE_SECURITY)
def api_update_incident(incident_id: str):
    """Update permitted fields on an existing incident (status, assignment, notes).

    Only fields listed in :data:`~app.constants.INCIDENT_UPDATE_FIELDS` are
    accepted; all others are silently ignored to prevent mass-assignment attacks.

    Args:
        incident_id: Path segment identifying the incident (e.g. ``"inc001"``).

    Returns:
        JSON envelope with updated ``id`` and ``status``, or 404 if not found.
    """
    body = request.get_json(silent=True) or {}
    update_data = {
        k: sanitize_string(str(v), 200)
        for k, v in body.items()
        if k in INCIDENT_UPDATE_FIELDS
    }
    if not update_data:
        err_body, status = error("No valid fields to update.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.update_incident(incident_id, update_data)
    if not result:
        body, status = error("Incident not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=result))


@bp.route("/api/security/incidents/<incident_id>/classify", methods=["POST"])
@require_role(ROLE_SECURITY)
def api_classify_incident(incident_id: str):
    """Classify an incident using AI and generate an Emergency Response plan.

    Runs the incident through the AI Incident Classification pipeline and
    persists the resulting type, severity, and recommended steps back to the
    incident record for the command-centre to act on.

    Args:
        incident_id: Path segment identifying the incident (e.g. ``"inc001"``).

    Returns:
        JSON envelope with classification type, severity, confidence score,
        response steps, required resources, and AI Decision Support payload.
    """
    result = _svc.classify_incident(incident_id)
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


@bp.route("/api/security/zones/heatmap")
@require_role(ROLE_SECURITY)
def api_heatmap():
    """Return zone density Threat Detection heatmap data for a venue.

    Query parameters:
        venue_id (str): Target venue (default: ``v001``).

    Returns:
        JSON envelope with per-zone occupancy percentages and bottleneck flags,
        suitable for rendering a visual heatmap overlay on the venue map.
    """
    venue_id = sanitize_string(
        request.args.get("venue_id", DEFAULT_VENUE_ID), max_length=10
    )
    result = _svc.get_zone_heatmap(venue_id)
    if "error" in result:
        err_body, status = error(result["error"], "DATA_001", status_code=404)
        return jsonify(err_body), status
    return jsonify(success(data=result))


@bp.route("/api/security/protocols/<incident_type>")
@require_role(ROLE_SECURITY)
def api_protocol(incident_type: str):
    """Return the Emergency Response protocol for a given incident type.

    Args:
        incident_type: Incident type slug (e.g. ``"crowd_surge"``, ``"medical"``).

    Returns:
        JSON envelope containing the protocol ``name``, response ``steps``,
        and ``resources`` required for that incident type.
    """
    incident_type = sanitize_string(incident_type, max_length=50).lower()
    protocol = _svc.get_protocol(incident_type)
    return jsonify(success(data={"incident_type": incident_type, "protocol": protocol}))
