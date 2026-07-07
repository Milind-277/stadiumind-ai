"""app/repositories/crowd_repo.py — JSON-backed CrowdSnapshot repository."""
from typing import Any, Dict

from app.models.crowd import CrowdSnapshot, ZoneDensity, DensityLevel
from .json_base import JSONRepository


class CrowdRepository(JSONRepository):
    def _get_filename(self) -> str:
        return "crowd.json"

    def _to_model(self, raw: Dict[str, Any]) -> CrowdSnapshot:
        zones = [
            ZoneDensity(
                zone_id=z["zone_id"],
                zone_name=z["zone_name"],
                current_count=z["current_count"],
                capacity=z["capacity"],
                density_level=DensityLevel(z["density_level"]),
                timestamp=z["timestamp"],
            )
            for z in raw.get("zones", [])
        ]
        return CrowdSnapshot(
            id=raw["id"],
            venue_id=raw["venue_id"],
            timestamp=raw["timestamp"],
            total_attendance=raw["total_attendance"],
            venue_capacity=raw["venue_capacity"],
            zones=zones,
            bottleneck_zones=raw.get("bottleneck_zones", []),
            alert_active=raw.get("alert_active", False),
        )

    def find_latest_by_venue(self, venue_id: str) -> CrowdSnapshot | None:
        """Return the most recent snapshot for a venue."""
        snapshots = self.find_where(lambda s: s.venue_id == venue_id)
        if not snapshots:
            return None
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)[0]
