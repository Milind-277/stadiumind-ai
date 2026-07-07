"""app/services/volunteer_service.py — Business logic for the Volunteer persona."""
import logging
from typing import Dict, List, Optional

from app.repositories.volunteer_repo import VolunteerRepository, TaskRepository
from app.repositories.incident_repo import IncidentRepository
from app.models.volunteer import TaskStatus
from app.utils.datetime_utils import utcnow_iso
from app.ai import ai_service

logger = logging.getLogger(__name__)


class VolunteerService:
    def __init__(self, data_dir: str = "data"):
        self.volunteers = VolunteerRepository(data_dir)
        self.tasks = TaskRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)

    def get_volunteer_by_id(self, volunteer_id: str) -> Optional[Dict]:
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
            return {"error": "Volunteer or task not found"}

        result = ai_service.ask("volunteer", "volunteer_guidance", {
            "volunteer_name": vol.name,
            "zone_name": task.zone_name,
            "task_title": task.title,
            "task_description": task.description,
            "priority": task.priority.value,
            "skills": ", ".join(vol.skills),
            "languages": ", ".join(vol.languages),
        })

        # Persist AI guidance back to the task
        self.tasks.update(task_id, {"ai_guidance": result.data.get("guidance", "")})

        return {
            "task_id": task_id,
            "guidance": result.data,
            "ai_powered": True,
            "fallback_used": result.fallback_used,
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
