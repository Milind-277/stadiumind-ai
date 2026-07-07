"""app/models/incident.py — Security incident domain models."""
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class IncidentType(str, Enum):
    CROWD_SURGE = "crowd_surge"
    MEDICAL = "medical"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FIRE_ALARM = "fire_alarm"
    SUSPICIOUS_ITEM = "suspicious_item"
    FIGHT = "fight"
    LOST_PERSON = "lost_person"
    STRUCTURAL = "structural"
    UNCLASSIFIED = "unclassified"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"


@dataclass
class Incident:
    id: str
    venue_id: str
    zone_id: str
    zone_name: str
    type: IncidentType
    severity: SeverityLevel
    status: IncidentStatus
    description: str
    reported_by: str       # volunteer_id or "system"
    reported_at: str       # ISO 8601
    assigned_to: Optional[str] = None
    resolved_at: Optional[str] = None
    ai_classification: Optional[str] = None
    ai_recommendation: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status in (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING)
