"""
app/blueprints/volunteer.py — Volunteer console routes (page views + JSON API).

Volunteer Features exposed here:
    * **Task Assignment**         — ``GET  /api/volunteer/tasks``
    * **Priority Management**     — tasks returned in priority-sorted order
    * **AI Task Recommendation**  — ``POST /api/volunteer/ai-guidance``
    * **Escalation Workflow**     — ``POST /api/volunteer/sos``
    * **Live Coordination**       — profile, zone, shift, and active task state

All routes are protected by :func:`~app.middleware.role_guard.require_role`
and delegate business logic exclusively to
:class:`~app.services.volunteer_service.VolunteerService`.
"""

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.constants import DEMO_VOLUNTEER_ID, ROLE_VOLUNTEER
from app.middleware.role_guard import require_role
from app.services.volunteer_service import VolunteerService
from app.utils.response import error, success
from app.utils.validators import require_fields, sanitize_string

bp = Blueprint("volunteer", __name__, url_prefix="/volunteer")
_svc = VolunteerService(Config.DATA_DIR)


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
@require_role(ROLE_VOLUNTEER)
def index():
    """Volunteer console home — Live Coordination profile and active tasks.

    Loads the demo volunteer's profile and their task list so they can
    immediately see their assigned zone, skills, and pending work.
    """
    vol = _svc.get_volunteer_by_id(DEMO_VOLUNTEER_ID)
    tasks = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return render_template("volunteer/console.html", volunteer=vol, tasks=tasks)


@bp.route("/tasks")
@require_role(ROLE_VOLUNTEER)
def tasks():
    """Volunteer task list page — full Priority Management view."""
    task_list = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return render_template("volunteer/tasks.html", tasks=task_list)


# ── API Routes ─────────────────────────────────────────────────────────────────


@bp.route("/api/volunteer/profile")
@require_role(ROLE_VOLUNTEER)
def api_profile():
    """Return the current volunteer's Live Coordination profile.

    Returns:
        JSON envelope with id, name, zone, skills, languages, status,
        and current shift information.
    """
    vol = _svc.get_volunteer_by_id(DEMO_VOLUNTEER_ID)
    if not vol:
        body, status = error("Volunteer not found.", "DATA_001", status_code=404)
        return jsonify(body), status
    return jsonify(success(data=vol))


@bp.route("/api/volunteer/tasks")
@require_role(ROLE_VOLUNTEER)
def api_tasks():
    """Return all Task Assignment records for the current volunteer.

    Tasks are returned in Priority Management order (urgent → high → medium → low).

    Returns:
        JSON envelope with a ``tasks`` list and ``total`` count.
    """
    volunteer_tasks = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return jsonify(
        success(data={"tasks": volunteer_tasks, "total": len(volunteer_tasks)})
    )


@bp.route("/api/volunteer/tasks/<task_id>", methods=["PATCH"])
@require_role(ROLE_VOLUNTEER)
def api_update_task(task_id: str):
    """Update the status of a volunteer task in the Task Assignment workflow.

    Request body (JSON):
        status (str): New task status (required). Must be a valid
            :class:`~app.models.volunteer.TaskStatus` value.

    Args:
        task_id: Path segment identifying the task (e.g. ``"t001"``).

    Returns:
        JSON envelope with updated ``id`` and ``status``, or 404 if not found.
    """
    body = request.get_json(silent=True) or {}
    new_status = sanitize_string(body.get("status", ""), max_length=20)
    if not new_status:
        err_body, status = error("'status' field is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.update_task_status(task_id, new_status)
    if not result:
        err_body, status = error(
            "Task not found or invalid status.", "DATA_001", status_code=404
        )
        return jsonify(err_body), status
    return jsonify(success(data=result))


@bp.route("/api/volunteer/ai-guidance", methods=["POST"])
@require_role(ROLE_VOLUNTEER)
def api_ai_guidance():
    """Generate AI Task Recommendation guidance for a specific task.

    Calls the AI pipeline to produce step-by-step task guidance, fan-facing
    phrases, safety notes, and escalation triggers tailored to the volunteer's
    skills and language preferences.

    Request body (JSON):
        task_id (str): ID of the task to generate guidance for (required).

    Returns:
        JSON envelope with AI guidance, steps, fan phrases, safety notes,
        escalation triggers, and Decision Engine decision support payload.
    """
    body = request.get_json(silent=True) or {}
    task_id = sanitize_string(body.get("task_id", ""), max_length=20)
    if not task_id:
        err_body, status = error("'task_id' is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.get_ai_task_guidance(DEMO_VOLUNTEER_ID, task_id)
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


@bp.route("/api/volunteer/sos", methods=["POST"])
@require_role(ROLE_VOLUNTEER)
def api_sos():
    """Submit an SOS Escalation Workflow alert, creating a high-severity incident.

    Immediately creates a new high-severity incident in the security incident
    log so the command centre can respond without delay.

    Request body (JSON):
        description (str): Description of the emergency (required).
        zone_id (str):     Zone ID where the emergency is occurring (required).
        zone_name (str):   Human-readable zone name (required).
        venue_id (str):    Venue identifier (required).

    Returns:
        JSON envelope confirming SOS receipt and returning the created incident ID.
    """
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "description", "zone_id", "zone_name", "venue_id")
    if missing:
        err_body, status = error(f"Field '{missing}' is required.", "VAL_001")
        return jsonify(err_body), status
    result = _svc.submit_sos(
        volunteer_id=DEMO_VOLUNTEER_ID,
        description=sanitize_string(body["description"], 500),
        zone_id=sanitize_string(body["zone_id"], 20),
        zone_name=sanitize_string(body["zone_name"], 100),
        venue_id=sanitize_string(body["venue_id"], 10),
    )
    return jsonify(success(data=result))
