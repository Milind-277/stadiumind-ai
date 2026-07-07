"""app/models/volunteer.py — Volunteer, Task, and Shift domain models."""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    id: str
    title: str
    description: str
    zone_id: str
    zone_name: str
    priority: TaskPriority
    status: TaskStatus
    assigned_to: str        # volunteer_id
    created_at: str         # ISO 8601
    due_by: Optional[str] = None
    completed_at: Optional[str] = None
    ai_guidance: Optional[str] = None


@dataclass
class Shift:
    id: str
    volunteer_id: str
    venue_id: str
    zone_id: str
    start_time: str         # ISO 8601
    end_time: str
    role: str               # "crowd_control" | "first_aid" | "wayfinding" | "accreditation"


@dataclass
class Volunteer:
    id: str
    name: str
    email: str
    venue_id: str
    zone_id: str
    zone_name: str
    skills: List[str]
    languages: List[str]
    shift: Optional[Shift] = None
    active_tasks: List[str] = field(default_factory=list)   # task IDs
    status: str = "available"   # "available" | "busy" | "off_duty"
