"""app/models/alert.py — Alert and notification domain models."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AlertPriority(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    EMERGENCY = "emergency"


class AlertTarget(str, Enum):
    ALL = "all"
    FAN = "fan"
    VOLUNTEER = "volunteer"
    SECURITY = "security"
    ORGANIZER = "organizer"


@dataclass
class Alert:
    id: str
    title: str
    message: str
    priority: AlertPriority
    target: AlertTarget
    venue_id: str
    zone_id: Optional[str]
    created_at: str  # ISO 8601
    created_by: str  # role that created the alert
    expires_at: Optional[str] = None
    acknowledged: bool = False
