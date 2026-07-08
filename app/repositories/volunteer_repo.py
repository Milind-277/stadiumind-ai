"""app/repositories/volunteer_repo.py — JSON-backed Volunteer and Task repositories."""

from typing import Any, Dict, List

from app.models.volunteer import (Shift, Task, TaskPriority, TaskStatus,
                                  Volunteer)

from .json_base import JSONRepository


class VolunteerRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "volunteers.json"

    def _to_model(self, raw: Dict[str, Any]) -> Volunteer:
        shift = None
        if raw.get("shift"):
            s = raw["shift"]
            shift = Shift(
                id=s["id"],
                volunteer_id=s["volunteer_id"],
                venue_id=s["venue_id"],
                zone_id=s["zone_id"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                role=s["role"],
            )
        return Volunteer(
            id=raw["id"],
            name=raw["name"],
            email=raw["email"],
            venue_id=raw["venue_id"],
            zone_id=raw["zone_id"],
            zone_name=raw["zone_name"],
            skills=raw.get("skills", []),
            languages=raw.get("languages", []),
            shift=shift,
            active_tasks=raw.get("active_tasks", []),
            status=raw.get("status", "available"),
        )

    def find_by_zone(self, zone_id: str) -> List[Volunteer]:
        return self.find_where(lambda v: v.zone_id == zone_id)

    def find_available(self) -> List[Volunteer]:
        return self.find_where(lambda v: v.status == "available")


class TaskRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "tasks.json"

    def _to_model(self, raw: Dict[str, Any]) -> Task:
        return Task(
            id=raw["id"],
            title=raw["title"],
            description=raw["description"],
            zone_id=raw["zone_id"],
            zone_name=raw["zone_name"],
            priority=TaskPriority(raw["priority"]),
            status=TaskStatus(raw["status"]),
            assigned_to=raw["assigned_to"],
            created_at=raw["created_at"],
            due_by=raw.get("due_by"),
            completed_at=raw.get("completed_at"),
            ai_guidance=raw.get("ai_guidance"),
        )

    def find_by_volunteer(self, volunteer_id: str) -> List[Task]:
        return self.find_where(lambda t: t.assigned_to == volunteer_id)

    def find_pending(self) -> List[Task]:
        return self.find_where(lambda t: t.status == TaskStatus.PENDING)
