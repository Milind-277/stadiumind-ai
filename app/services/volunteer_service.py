"""
app/services/volunteer_service.py — Business logic for the Volunteer persona.

This service implements all Volunteer Features:

    * **Task Assignment**        — :meth:`get_tasks_for_volunteer`
    * **Priority Management**    — tasks returned in priority-sorted order
    * **AI Task Recommendation** — :meth:`get_ai_task_guidance`
    * **Escalation Workflow**    — :meth:`submit_sos`
    * **Live Coordination**      — :meth:`get_volunteer_by_id`, :meth:`get_all_volunteers`

The service composes :class:`~app.repositories.volunteer_repo.VolunteerRepository`,
:class:`~app.repositories.volunteer_repo.TaskRepository`,
:class:`~app.repositories.incident_repo.IncidentRepository`, and
:class:`~app.ai.decision_engine.DecisionEngine`.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai import ai_service
from app.ai.decision_engine import DecisionEngine
from app.constants import (
    INCIDENT_DEFAULT_TYPE,
    INTENT_VOLUNTEER_GUIDANCE,
    ROLE_VOLUNTEER,
    SOS_DEFAULT_SEVERITY,
    SOS_DESCRIPTION_PREFIX,
    SOS_INCIDENT_ID_PREFIX,
    TASK_STATUS_COMPLETED,
    VOLUNTEER_MAX_ACCESSIBILITY_ITEMS,
)
from app.models.volunteer import TaskStatus
from app.repositories.incident_repo import IncidentRepository
from app.repositories.volunteer_repo import TaskRepository, VolunteerRepository
from app.utils.datetime_utils import utcnow_iso
from app.utils.serializers import PRIORITY_ORDER

logger = logging.getLogger(__name__)


class VolunteerService:
    """Volunteer-facing business logic for tasks, guidance, and SOS escalation.

    Attributes:
        volunteers:      Repository for volunteer profiles.
        tasks:           Repository for volunteer tasks.
        incidents:       Repository for security incidents (SOS creates incidents).
        decision_engine: Deterministic AI decision engine for volunteer recommendations.
    """

    def __init__(self, data_dir: str = "data") -> None:
        """Initialise repositories and the Decision Engine.

        Args:
            data_dir: Path to the directory containing JSON data files.
        """
        self.volunteers = VolunteerRepository(data_dir)
        self.tasks = TaskRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_decision_support(self, volunteer: Any, task: Any) -> Dict[str, Any]:
        """Build a JSON-serialisable Decision Support payload for a volunteer.

        Derives accessibility needs from the volunteer's skill set and
        preferred language from their profile.

        Args:
            volunteer: A ``Volunteer`` model instance.
            task:      The associated ``Task`` model instance.

        Returns:
            Decision support dict with gate, navigation, crowd-avoidance,
            emergency, accessibility, and transportation recommendations.
        """
        accessibility_needs = [
            "accessibility_support"
            for skill in volunteer.skills
            if "accessibility" in skill.lower()
        ][:VOLUNTEER_MAX_ACCESSIBILITY_ITEMS]
        language = volunteer.languages[0] if volunteer.languages else "English"

        return self.decision_engine.safe_decide(
            user_role=ROLE_VOLUNTEER,
            venue_id=volunteer.venue_id,
            accessibility_needs=accessibility_needs,
            language=language,
            fallback_overrides={
                "navigation_advice": [
                    "Follow the closest marked route to your assigned zone."
                ],
                "crowd_avoidance": [
                    "Avoid high-density areas until directed otherwise."
                ],
                "accessibility_recommendations": [
                    "Ask a supervisor for assistance if needed."
                ],
                "transportation_suggestion": "Use the venue's nearest transit option.",
            },
        )

    @staticmethod
    def _build_sos_incident_id() -> str:
        """Generate a timestamped SOS incident ID.

        Returns:
            A unique string ID prefixed with :data:`~app.constants.SOS_INCIDENT_ID_PREFIX`.
        """
        return f"{SOS_INCIDENT_ID_PREFIX}{utcnow_iso().replace(':', '').replace('-', '')[:14]}"

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_volunteer_by_id(self, volunteer_id: str) -> Optional[Dict[str, Any]]:
        """Return a volunteer's Live Coordination profile as a serialisable dict.

        Args:
            volunteer_id: Unique volunteer identifier.

        Returns:
            Profile dict with id, name, zone, skills, languages, status, and
            shift information, or ``None`` if not found.
        """
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
            "shift": (
                {
                    "role": vol.shift.role,
                    "start_time": vol.shift.start_time,
                    "end_time": vol.shift.end_time,
                }
                if vol.shift
                else None
            ),
        }

    def get_all_volunteers(self) -> List[Dict[str, Any]]:
        """Return all volunteers with basic Live Coordination info.

        Returns:
            List of volunteer summary dicts including active task count.
        """
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

    def get_tasks_for_volunteer(self, volunteer_id: str) -> List[Dict[str, Any]]:
        """Return all Task Assignment records for a volunteer in Priority Management order.

        Args:
            volunteer_id: Unique volunteer identifier.

        Returns:
            List of task dicts sorted urgent → high → medium → low.
        """
        tasks = self.tasks.find_by_volunteer(volunteer_id)
        tasks.sort(key=lambda t: PRIORITY_ORDER.get(t.priority.value, 9))
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

    def update_task_status(
        self, task_id: str, new_status: str
    ) -> Optional[Dict[str, Any]]:
        """Update a task's status in the Task Assignment workflow.

        Automatically stamps ``completed_at`` when status transitions to
        :data:`~app.constants.TASK_STATUS_COMPLETED`.

        Args:
            task_id:    Unique task identifier.
            new_status: New status string; must be a valid
                :class:`~app.models.volunteer.TaskStatus` value.

        Returns:
            Dict with ``id`` and ``status`` on success, or ``None`` when the
            task is not found or the status is invalid.
        """
        valid_statuses = {s.value for s in TaskStatus}
        if new_status not in valid_statuses:
            return None
        data: Dict[str, Any] = {"status": new_status}
        if new_status == TASK_STATUS_COMPLETED:
            data["completed_at"] = utcnow_iso()
        updated = self.tasks.update(task_id, data)
        if not updated:
            return None
        return {"id": updated.id, "status": updated.status.value}

    def get_ai_task_guidance(
        self, volunteer_id: str, task_id: str
    ) -> Dict[str, Any]:
        """Generate AI Task Recommendation guidance for a specific task.

        Calls the AI pipeline with volunteer and task context to produce
        step-by-step instructions, fan-facing phrases, safety notes, and
        escalation triggers.  Persists the guidance summary back to the task.

        Args:
            volunteer_id: Unique volunteer identifier.
            task_id:      Unique task identifier.

        Returns:
            Dict with ``guidance`` payload, ``ai_powered`` flag, ``fallback_used``
            flag, and Decision Support.  Returns ``{"error": "..."}`` when
            volunteer or task is not found.
        """
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
            result = ai_service.ask(
                ROLE_VOLUNTEER,
                INTENT_VOLUNTEER_GUIDANCE,
                {
                    "volunteer_name": vol.name,
                    "zone_name": task.zone_name,
                    "task_title": task.title,
                    "task_description": task.description,
                    "priority": task.priority.value,
                    "skills": ", ".join(vol.skills),
                    "languages": ", ".join(vol.languages),
                },
            )
            guidance = result.data
            fallback_used = result.fallback_used
        except Exception:
            logger.exception(
                "Volunteer guidance AI fallback volunteer_id=%s task_id=%s",
                volunteer_id,
                task_id,
            )
            guidance = self._guidance_fallback(task, decision_support)
            fallback_used = True

        # Persist AI guidance summary back to the task record
        self.tasks.update(task_id, {"ai_guidance": guidance.get("guidance", "")})

        return {
            "task_id": task_id,
            "guidance": guidance,
            "ai_powered": True,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    @staticmethod
    def _guidance_fallback(
        task: Any,
        decision_support: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a structured AI guidance fallback when the AI pipeline fails.

        Args:
            task:             Task model instance.
            decision_support: Decision Engine payload.

        Returns:
            Guidance dict with steps derived from Decision Support output.
        """
        return {
            "guidance": (
                f"Follow the decision support plan for {task.title} near {task.zone_name}."
            ),
            "steps": (
                decision_support["navigation_advice"]
                + decision_support["crowd_avoidance"]
                + decision_support["emergency_actions"]
            )[:5],
            "fan_phrases": [
                "How can I help you today?",
                "Please follow me, I'll show you the way.",
            ],
            "safety_notes": (
                "Keep routes clear and escalate any safety concern immediately."
            ),
            "escalate_if": (
                "Any situation involving physical danger, medical emergency, or security threat."
            ),
        }

    def submit_sos(
        self,
        volunteer_id: str,
        description: str,
        zone_id: str,
        zone_name: str,
        venue_id: str,
    ) -> Dict[str, Any]:
        """Submit an SOS Escalation Workflow alert, creating a high-severity incident.

        Immediately creates a new incident in the security incident log so the
        command centre is notified without delay.

        Args:
            volunteer_id: ID of the volunteer submitting the SOS.
            description:  Description of the emergency situation.
            zone_id:      Zone identifier where the emergency is occurring.
            zone_name:    Human-readable zone name.
            venue_id:     Venue identifier.

        Returns:
            Dict confirming SOS submission and containing the created ``incident_id``.
        """
        incident_data = {
            "id": self._build_sos_incident_id(),
            "venue_id": venue_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "type": INCIDENT_DEFAULT_TYPE,
            "severity": SOS_DEFAULT_SEVERITY,
            "status": "open",
            "description": f"{SOS_DESCRIPTION_PREFIX}{description}",
            "reported_by": volunteer_id,
            "reported_at": utcnow_iso(),
            "notes": [],
        }
        self.incidents.save(incident_data)
        logger.warning(
            "SOS escalation from volunteer %s in zone %s: %s",
            volunteer_id,
            zone_name,
            description[:100],
        )
        return {
            "sos_submitted": True,
            "incident_id": incident_data["id"],
            "message": "SOS received. Security team has been alerted. Stay safe.",
        }
