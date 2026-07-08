"""app/repositories/incident_repo.py — JSON-backed Incident repository."""

from typing import Any, Dict, List

from app.models.incident import (Incident, IncidentStatus, IncidentType,
                                 SeverityLevel)

from .json_base import JSONRepository


class IncidentRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "incidents.json"

    def _to_model(self, raw: Dict[str, Any]) -> Incident:
        return Incident(
            id=raw["id"],
            venue_id=raw["venue_id"],
            zone_id=raw["zone_id"],
            zone_name=raw["zone_name"],
            type=IncidentType(raw["type"]),
            severity=SeverityLevel(raw["severity"]),
            status=IncidentStatus(raw["status"]),
            description=raw["description"],
            reported_by=raw["reported_by"],
            reported_at=raw["reported_at"],
            assigned_to=raw.get("assigned_to"),
            resolved_at=raw.get("resolved_at"),
            ai_classification=raw.get("ai_classification"),
            ai_recommendation=raw.get("ai_recommendation"),
            notes=raw.get("notes", []),
        )

    def find_active(self) -> List[Incident]:
        """Return all open or investigating incidents."""
        return self.find_where(lambda i: i.is_active)

    def find_by_venue(self, venue_id: str) -> List[Incident]:
        return self.find_where(lambda i: i.venue_id == venue_id)

    def find_by_severity(self, severity: SeverityLevel) -> List[Incident]:
        return self.find_where(lambda i: i.severity == severity)
