"""app/blueprints/volunteer.py — Volunteer console routes (pages + API)."""
from flask import Blueprint, render_template, request, jsonify, session

from app.middleware.role_guard import require_role
from app.services.volunteer_service import VolunteerService
from app.utils.response import success, error
from app.utils.validators import sanitize_string, require_fields
from app.config import Config

bp = Blueprint("volunteer", __name__, url_prefix="/volunteer")
_svc = VolunteerService(Config.DATA_DIR)

# Demo: use vol001 as the "logged-in" volunteer for the demo
DEMO_VOLUNTEER_ID = "vol001"


# ── Page Routes ────────────────────────────────────────────────────────────────

@bp.route("/")
@require_role("volunteer")
def index():
    vol = _svc.get_volunteer_by_id(DEMO_VOLUNTEER_ID)
    tasks = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return render_template("volunteer/console.html", volunteer=vol, tasks=tasks)


@bp.route("/tasks")
@require_role("volunteer")
def tasks():
    tasks = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return render_template("volunteer/tasks.html", tasks=tasks)


# ── API Routes ─────────────────────────────────────────────────────────────────

@bp.route("/api/volunteer/profile")
@require_role("volunteer")
def api_profile():
    vol = _svc.get_volunteer_by_id(DEMO_VOLUNTEER_ID)
    if not vol:
        return jsonify(*error("Volunteer not found.", "DATA_001", status_code=404))
    return jsonify(success(data=vol))


@bp.route("/api/volunteer/tasks")
@require_role("volunteer")
def api_tasks():
    tasks = _svc.get_tasks_for_volunteer(DEMO_VOLUNTEER_ID)
    return jsonify(success(data={"tasks": tasks, "total": len(tasks)}))


@bp.route("/api/volunteer/tasks/<task_id>", methods=["PATCH"])
@require_role("volunteer")
def api_update_task(task_id: str):
    body = request.get_json(silent=True) or {}
    new_status = sanitize_string(body.get("status", ""), max_length=20)
    if not new_status:
        return jsonify(*error("'status' field is required.", "VAL_001"))
    result = _svc.update_task_status(task_id, new_status)
    if not result:
        return jsonify(*error("Task not found or invalid status.", "DATA_001", status_code=404))
    return jsonify(success(data=result))


@bp.route("/api/volunteer/ai-guidance", methods=["POST"])
@require_role("volunteer")
def api_ai_guidance():
    body = request.get_json(silent=True) or {}
    task_id = sanitize_string(body.get("task_id", ""), max_length=20)
    if not task_id:
        return jsonify(*error("'task_id' is required.", "VAL_001"))
    result = _svc.get_ai_task_guidance(DEMO_VOLUNTEER_ID, task_id)
    if "error" in result:
        return jsonify(*error(result["error"], "DATA_001", status_code=404))
    return jsonify(success(data=result, ai_powered=True, fallback_used=result.get("fallback_used", False)))


@bp.route("/api/volunteer/sos", methods=["POST"])
@require_role("volunteer")
def api_sos():
    body = request.get_json(silent=True) or {}
    missing = require_fields(body, "description", "zone_id", "zone_name", "venue_id")
    if missing:
        return jsonify(*error(f"Field '{missing}' is required.", "VAL_001"))
    result = _svc.submit_sos(
        volunteer_id=DEMO_VOLUNTEER_ID,
        description=sanitize_string(body["description"], 500),
        zone_id=sanitize_string(body["zone_id"], 20),
        zone_name=sanitize_string(body["zone_name"], 100),
        venue_id=sanitize_string(body["venue_id"], 10),
    )
    return jsonify(success(data=result))
