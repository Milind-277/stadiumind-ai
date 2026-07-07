"""app/models/crowd.py — Crowd density and analytics domain models."""
from dataclasses import dataclass
from enum import Enum
from typing import List


class DensityLevel(str, Enum):
    LOW = "low"           # < 40% capacity
    MODERATE = "moderate" # 40–70%
    HIGH = "high"         # 70–85%
    CRITICAL = "critical" # > 85%


@dataclass
class ZoneDensity:
    zone_id: str
    zone_name: str
    current_count: int
    capacity: int
    density_level: DensityLevel
    timestamp: str         # ISO 8601

    @property
    def occupancy_pct(self) -> float:
        if self.capacity == 0:
            return 0.0
        return round((self.current_count / self.capacity) * 100, 1)


@dataclass
class CrowdSnapshot:
    id: str
    venue_id: str
    timestamp: str
    total_attendance: int
    venue_capacity: int
    zones: List[ZoneDensity]
    bottleneck_zones: List[str]    # zone_ids flagged as bottlenecks
    alert_active: bool

    @property
    def overall_occupancy_pct(self) -> float:
        if self.venue_capacity == 0:
            return 0.0
        return round((self.total_attendance / self.venue_capacity) * 100, 1)
