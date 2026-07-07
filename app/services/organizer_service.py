"""app/services/organizer_service.py — Business logic for the Organizer persona."""
import logging
import random
from typing import Dict, List

from app.repositories.crowd_repo import CrowdRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.volunteer_repo import VolunteerRepository, TaskRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.utils.datetime_utils import utcnow_iso
from app.ai import ai_service

logger = logging.getLogger(__name__)


class OrganizerService:
    def __init__(self, data_dir: str = "data"):
        self.crowds = CrowdRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)
        self.volunteers = VolunteerRepository(data_dir)
        self.tasks = TaskRepository(data_dir)
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)

    def get_dashboard_summary(self) -> Dict:
        """Return aggregated dashboard data for all venues."""
        all_incidents = self.incidents.find_all()
        active_incidents = [i for i in all_incidents if i.is_active]
        critical = [i for i in active_incidents if i.severity.value == "critical"]
        all_volunteers = self.volunteers.find_all()
        available_vols = [v for v in all_volunteers if v.status == "available"]
        live_matches = [m for m in self.matches.find_all() if m.status == "live"]

        # Collect snapshots for all venues
        venue_summaries = []
        for venue in self.venues.find_all():
            snapshot = self.crowds.find_latest_by_venue(venue.id)
            if snapshot:
                venue_summaries.append({
                    "venue_id": venue.id,
                    "venue_name": venue.name,
                    "city": venue.city,
                    "attendance": snapshot.total_attendance,
                    "capacity": snapshot.venue_capacity,
                    "occupancy_pct": snapshot.overall_occupancy_pct,
                    "alert_active": snapshot.alert_active,
                    "bottleneck_count": len(snapshot.bottleneck_zones),
                })

        return {
            "total_active_incidents": len(active_incidents),
            "critical_incidents": len(critical),
            "total_volunteers": len(all_volunteers),
            "available_volunteers": len(available_vols),
            "live_matches": len(live_matches),
            "venues": venue_summaries,
            "alert_active": any(v["alert_active"] for v in venue_summaries),
        }

    def get_live_crowd(self, venue_id: str = None) -> Dict:
        """Return live crowd data. Applies small random jitter to simulate real-time."""
        if venue_id:
            snapshot = self.crowds.find_latest_by_venue(venue_id)
            snapshots = [snapshot] if snapshot else []
        else:
            # Get latest snapshot per venue
            snapshots = []
            for venue in self.venues.find_all():
                s = self.crowds.find_latest_by_venue(venue.id)
                if s:
                    snapshots.append(s)

        result = []
        for snap in snapshots:
            zones_data = []
            for z in snap.zones:
                # Simulate real-time jitter (±2%)
                jitter = random.randint(-int(z.capacity * 0.02), int(z.capacity * 0.02))
                simulated_count = max(0, min(z.capacity, z.current_count + jitter))
                zones_data.append({
                    "zone_id": z.zone_id,
                    "zone_name": z.zone_name,
                    "current_count": simulated_count,
                    "capacity": z.capacity,
                    "occupancy_pct": round((simulated_count / z.capacity) * 100, 1) if z.capacity else 0,
                    "density_level": z.density_level.value,
                })
            result.append({
                "venue_id": snap.venue_id,
                "timestamp": utcnow_iso(),
                "total_attendance": snap.total_attendance,
                "venue_capacity": snap.venue_capacity,
                "occupancy_pct": snap.overall_occupancy_pct,
                "alert_active": snap.alert_active,
                "bottleneck_zones": snap.bottleneck_zones,
                "zones": zones_data,
            })
        return {"venues": result}

    def get_ai_crowd_analysis(self, venue_id: str) -> Dict:
        """Get AI-powered crowd analysis for a venue."""
        snapshot = self.crowds.find_latest_by_venue(venue_id)
        venue = self.venues.find_by_id(venue_id)
        if not snapshot or not venue:
            return {"error": "Venue or crowd data not found"}

        zone_text = "\n".join(
            f"- {z.zone_name}: {z.current_count}/{z.capacity} ({z.occupancy_pct}%) — {z.density_level.value}"
            for z in snapshot.zones
        )
        bottleneck_text = ", ".join(snapshot.bottleneck_zones) or "None"

        result = ai_service.ask("organizer", "crowd_analysis", {
            "venue_name": venue.name,
            "timestamp": snapshot.timestamp,
            "total_attendance": str(snapshot.total_attendance),
            "venue_capacity": str(snapshot.venue_capacity),
            "occupancy_pct": str(snapshot.overall_occupancy_pct),
            "zone_data": zone_text,
            "bottleneck_zones": bottleneck_text,
        })

        return {
            "venue_name": venue.name,
            "analysis": result.data,
            "ai_powered": True,
            "from_cache": result.from_cache,
            "fallback_used": result.fallback_used,
        }

    def generate_event_briefing(self, venue_id: str) -> Dict:
        """Generate an AI operational briefing for a venue."""
        venue = self.venues.find_by_id(venue_id)
        if not venue:
            return {"error": "Venue not found"}

        snapshot = self.crowds.find_latest_by_venue(venue_id)
        incidents = self.incidents.find_by_venue(venue_id)
        active_incidents = [i for i in incidents if i.is_active]
        volunteers = self.volunteers.find_where(lambda v: v.venue_id == venue_id)
        matches = self.matches.find_where(lambda m: m.venue_id == venue_id)
        live_match = next((m for m in matches if m.status == "live"), None)

        match_summary = f"{live_match.home_team.name} vs {live_match.away_team.name} (LIVE)" if live_match else "No live match"
        crowd_summary = f"Attendance: {snapshot.total_attendance:,}/{snapshot.venue_capacity:,} ({snapshot.overall_occupancy_pct}%)" if snapshot else "N/A"
        incident_summary = "\n".join(
            f"- [{i.severity.value.upper()}] {i.type.value}: {i.description[:80]}"
            for i in active_incidents[:5]
        ) or "No active incidents"
        vol_summary = f"{len(volunteers)} deployed, {sum(1 for v in volunteers if v.status == 'available')} available"

        result = ai_service.ask("organizer", "event_briefing", {
            "venue_name": venue.name,
            "city": venue.city,
            "country": venue.country,
            "event_date": utcnow_iso()[:10],
            "match_summary": match_summary,
            "total_attendance": str(snapshot.total_attendance if snapshot else 0),
            "venue_capacity": str(venue.capacity),
            "occupancy_pct": str(snapshot.overall_occupancy_pct if snapshot else 0),
            "crowd_summary": crowd_summary,
            "incident_count": str(len(active_incidents)),
            "incident_summary": incident_summary,
            "volunteer_summary": vol_summary,
        })

        return {
            "venue_name": venue.name,
            "briefing": result.data,
            "ai_powered": True,
            "from_cache": result.from_cache,
            "fallback_used": result.fallback_used,
        }

    def broadcast_alert(self, title: str, message: str, priority: str, venue_id: str) -> Dict:
        """Create and broadcast an alert."""
        alert = {
            "id": f"alrt_{utcnow_iso().replace(':', '').replace('-', '')[:14]}",
            "title": title,
            "message": message,
            "priority": priority,
            "venue_id": venue_id,
            "created_at": utcnow_iso(),
            "created_by": "organizer",
        }
        logger.info("Alert broadcast: %s — %s", priority.upper(), title)
        return {"alert": alert, "broadcast": True}

    def get_all_incidents(self) -> List[Dict]:
        """Return all incidents sorted by severity then recency."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        incidents = self.incidents.find_all()
        incidents.sort(key=lambda i: (severity_order.get(i.severity.value, 9), i.reported_at), reverse=False)
        return [
            {
                "id": i.id,
                "venue_id": i.venue_id,
                "zone_name": i.zone_name,
                "type": i.type.value,
                "severity": i.severity.value,
                "status": i.status.value,
                "description": i.description,
                "reported_at": i.reported_at,
                "is_active": i.is_active,
            }
            for i in incidents
        ]
