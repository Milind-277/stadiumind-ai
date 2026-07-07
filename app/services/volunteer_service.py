"""app/services/volunteer_service.py — Business logic for the Volunteer persona."""
import logging
from typing import Dict, List, Optional

from app.ai.decision_engine import DecisionEngine
from app.ai import ai_service
from app.repositories.volunteer_repo import VolunteerRepository, TaskRepository
from app.repositories.incident_repo import IncidentRepository
from app.models.volunteer import TaskStatus
from app.utils.datetime_utils import utcnow_iso

logger = logging.getLogger(__name__)


class VolunteerService:
    """Volunteer-facing business logic for tasks, guidance, and SOS flows."""

    def __init__(self, data_dir: str = "data"):
        """Initialise repositories and the decision engine."""
        self.volunteers = VolunteerRepository(data_dir)
        self.tasks = TaskRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    def _build_decision_support(self, volunteer, task) -> Dict:
        """Build a JSON-serializable decision support payload for volunteers."""
        accessibility_needs = []
        if any("accessibility" in skill.lower() for skill in volunteer.skills):
            accessibility_needs.append("accessibility_support")
        language = volunteer.languages[0] if volunteer.languages else "English"

        try:
            context = self.decision_engine.build_context(
                user_role="volunteer",
                venue_id=volunteer.venue_id,
                accessibility_needs=accessibility_needs,
                language=language,
            )
            decision = self.decision_engine.decide(context)
            logger.info(
                "Decision support built for volunteer service volunteer_id=%s task_id=%s best_gate=%s",
                volunteer.id,
                task.id,
                decision["best_gate"],
            )
            return decision
        except Exception as exc:
            logger.exception(
                "Decision support fallback for volunteer service volunteer_id=%s task_id=%s",
                volunteer.id,
                task.id,
            )
            return {
                "best_gate": "Main gate",
                "navigation_advice": ["Follow the closest marked route to your assigned zone."],
                "crowd_avoidance": ["Avoid high-density areas until directed otherwise."],
                "emergency_actions": ["No immediate emergency action required."],
                "accessibility_recommendations": ["Ask a supervisor for assistance if needed."],
                "transportation_suggestion": "Use the venue's nearest transit option.",
                "error": str(exc),
            }

    def get_volunteer_by_id(self, volunteer_id: str) -> Optional[Dict]:
        """Return a volunteer profile as a JSON-serializable dictionary."""
        vol = self.volunteers.find_by_id(volunteer_id)
        if not vol:
            return None
        return {
            "id": vol.id,
            "name": vol.name,
            "zone_id": vol.zone_id,
            "zone_name": vol.zone_name,
            "skills": vol.skills,
            "languages": vol.languages,
            "status": vol.status,
            "shift": {
                "role": vol.shift.role,
                "start_time": vol.shift.start_time,
                "end_time": vol.shift.end_time,
            } if vol.shift else None,
        }

    def get_all_volunteers(self) -> List[Dict]:
        """Return all volunteers with basic info."""
        return [
            {
                "id": v.id,
                "name": v.name,
                "zone_name": v.zone_name,
                "status": v.status,
                "skills": v.skills,
                "active_task_count": len(v.active_tasks),
            }
            for v in self.volunteers.find_all()
        ]

    def get_tasks_for_volunteer(self, volunteer_id: str) -> List[Dict]:
        """Return all tasks assigned to a volunteer, sorted by priority."""
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        tasks = self.tasks.find_by_volunteer(volunteer_id)
        tasks.sort(key=lambda t: priority_order.get(t.priority.value, 9))
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "zone_name": t.zone_name,
                "priority": t.priority.value,
                "status": t.status.value,
                "due_by": t.due_by,
                "ai_guidance": t.ai_guidance,
            }
            for t in tasks
        ]

    def update_task_status(self, task_id: str, new_status: str) -> Optional[Dict]:
        """Update a task's status."""
        valid_statuses = {s.value for s in TaskStatus}
        if new_status not in valid_statuses:
            return None
        data = {"status": new_status}
        if new_status == "completed":
            data["completed_at"] = utcnow_iso()
        updated = self.tasks.update(task_id, data)
        if not updated:
            return None
        return {"id": updated.id, "status": updated.status.value}

    def get_ai_task_guidance(self, volunteer_id: str, task_id: str) -> Dict:
        """Get AI guidance for a specific task."""
        vol = self.volunteers.find_by_id(volunteer_id)
        task = self.tasks.find_by_id(task_id)
        if not vol or not task:
            logger.warning(
                "Task guidance requested for missing volunteer_id=%s task_id=%s",
                volunteer_id,
                task_id,
            )
            return {"error": "Volunteer or task not found"}

        decision_support = self._build_decision_support(vol, task)

        try:
            result = ai_service.ask("volunteer", "volunteer_guidance", {
                "volunteer_name": vol.name,
                "zone_name": task.zone_name,
                "task_title": task.title,
                "task_description": task.description,
                "priority": task.priority.value,
                "skills": ", ".join(vol.skills),
                "languages": ", ".join(vol.languages),
            })
            guidance = result.data
            fallback_used = result.fallback_used
        except Exception:
            logger.exception(
                "Volunteer guidance AI fallback volunteer_id=%s task_id=%s",
                volunteer_id,
                task_id,
            )
            guidance = {
                "guidance": (
                    f"Follow the decision support plan for {task.title} near {task.zone_name}."
                ),
                "steps": (
                    decision_support["navigation_advice"]
                    + decision_support["crowd_avoidance"]
                    + decision_support["emergency_actions"]
                )[:5],
                "fan_phrases": ["How can I help you today?", "Please follow me, I'll show you the way."],
                "safety_notes": "Keep routes clear and escalate any safety concern immediately.",
                "escalate_if": "Any situation involving physical danger, medical emergency, or security threat.",
            }
            fallback_used = True

        # Persist AI guidance back to the task
        self.tasks.update(task_id, {"ai_guidance": guidance.get("guidance", "")})

        return {
            "task_id": task_id,
            "guidance": guidance,
            "ai_powered": True,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    def submit_sos(self, volunteer_id: str, description: str, zone_id: str, zone_name: str, venue_id: str) -> Dict:
        """Submit an SOS escalation creating a new incident."""
        incident_data = {
            "id": f"inc_sos_{utcnow_iso().replace(':', '').replace('-', '')[:14]}",
            "venue_id": venue_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "type": "unclassified",
            "severity": "high",
            "status": "open",
            "description": f"[SOS ESCALATION] {description}",
            "reported_by": volunteer_id,
            "reported_at": utcnow_iso(),
            "notes": [],
        }
        self.incidents.save(incident_data)
        logger.warning(
            "SOS escalation from volunteer %s in zone %s: %s",
            volunteer_id, zone_name, description[:100]
        )
        return {
            "sos_submitted": True,
            "incident_id": incident_data["id"],
            "message": "SOS received. Security team has been alerted. Stay safe.",
        }
