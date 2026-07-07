"""app/services/fan_service.py — Business logic for the Fan persona."""
import logging
from typing import Dict, List, Optional

from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.repositories.crowd_repo import CrowdRepository
from app.utils.datetime_utils import format_match_time, time_until
from app.ai import ai_service

logger = logging.getLogger(__name__)


class FanService:
    def __init__(self, data_dir: str = "data"):
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)
        self.crowds = CrowdRepository(data_dir)

    def get_all_matches(self) -> List[Dict]:
        """Return all matches with formatted times and status."""
        result = []
        for m in self.matches.find_all():
            result.append({
                "id": m.id,
                "home_team": {"name": m.home_team.name, "code": m.home_team.code, "flag": m.home_team.flag_emoji},
                "away_team": {"name": m.away_team.name, "code": m.away_team.code, "flag": m.away_team.flag_emoji},
                "venue_id": m.venue_id,
                "venue_name": m.venue_name,
                "kickoff_display": format_match_time(m.kickoff_utc),
                "time_until": time_until(m.kickoff_utc),
                "stage": m.stage,
                "group": m.group,
                "status": m.status,
                "score": m.score_display,
                "is_live": m.is_live,
                "attendance": m.attendance,
                "highlights": m.highlights,
            })
        return result

    def get_match_detail(self, match_id: str) -> Optional[Dict]:
        """Return full match detail with venue info."""
        m = self.matches.find_by_id(match_id)
        if not m:
            return None
        venue = self.venues.find_by_id(m.venue_id)
        return {
            "id": m.id,
            "home_team": {"name": m.home_team.name, "code": m.home_team.code, "flag": m.home_team.flag_emoji, "group": m.home_team.group},
            "away_team": {"name": m.away_team.name, "code": m.away_team.code, "flag": m.away_team.flag_emoji, "group": m.away_team.group},
            "venue": {
                "name": venue.name if venue else m.venue_name,
                "city": venue.city if venue else "",
                "country": venue.country if venue else "",
                "nearest_transit": venue.nearest_transit if venue else "",
            } if venue else {"name": m.venue_name},
            "kickoff_display": format_match_time(m.kickoff_utc),
            "stage": m.stage,
            "group": m.group,
            "status": m.status,
            "score": m.score_display,
            "attendance": m.attendance,
            "highlights": m.highlights,
        }

    def get_wayfinding(self, venue_id: str, destination: str) -> Dict:
        """Return AI-enhanced wayfinding advice for a venue destination."""
        venue = self.venues.find_by_id(venue_id)
        if not venue:
            return {"error": "Venue not found"}

        # Build venue context for AI
        zones_text = "\n".join(
            f"- {z.name} (Level {z.level}, {'Accessible' if z.accessible else 'Not accessible'})"
            for z in venue.zones
        )
        gates_text = "\n".join(
            f"- {g.name} ({g.location}, {'Accessible' if g.accessible else 'Standard'}, opens {g.open_time})"
            for g in venue.gates
        )

        result = ai_service.ask("fan", "fan_chat", {
            "venue_context": f"Venue: {venue.name}\nGates:\n{gates_text}\nZones:\n{zones_text}\nAccessibility services: {', '.join(venue.accessibility_services[:3])}",
            "match_context": "Fan is requesting wayfinding assistance.",
            "user_input": f"How do I get to {destination}?",
        })

        return {
            "venue_name": venue.name,
            "destination": destination,
            "ai_guidance": result.data,
            "ai_powered": True,
            "fallback_used": result.fallback_used,
            "gates": [{"name": g.name, "location": g.location, "accessible": g.accessible} for g in venue.gates],
            "accessibility_services": venue.accessibility_services,
        }

    def get_venue_info(self, venue_id: str) -> Optional[Dict]:
        """Return venue details for the fan portal."""
        venue = self.venues.find_by_id(venue_id)
        if not venue:
            return None
        crowd = self.crowds.find_latest_by_venue(venue_id)
        return {
            "id": venue.id,
            "name": venue.name,
            "city": venue.city,
            "country": venue.country,
            "capacity": venue.capacity,
            "nearest_transit": venue.nearest_transit,
            "accessibility_services": venue.accessibility_services,
            "gates": [{"id": g.id, "name": g.name, "location": g.location, "accessible": g.accessible, "open_time": g.open_time} for g in venue.gates],
            "food_courts": [
                {
                    "id": f.id, "name": f.name,
                    "cuisine_types": f.cuisine_types,
                    "halal": f.halal_available,
                    "vegetarian": f.vegetarian_available,
                    "wait_time": f.wait_time_minutes,
                }
                for f in venue.food_courts
            ],
            "current_occupancy_pct": crowd.overall_occupancy_pct if crowd else None,
        }

    def chat(self, message: str, venue_id: str) -> Dict:
        """Process fan chat message through AI assistant."""
        venue = self.venues.find_by_id(venue_id) if venue_id else None
        matches = self.get_all_matches()
        live_matches = [m for m in matches if m["is_live"]]

        venue_ctx = "No specific venue selected."
        if venue:
            food_info = ", ".join(f.name for f in venue.food_courts)
            gate_info = ", ".join(f"{g.name} ({g.location})" for g in venue.gates)
            venue_ctx = (
                f"Venue: {venue.name}, {venue.city}, {venue.country}\n"
                f"Capacity: {venue.capacity:,}\n"
                f"Gates: {gate_info}\n"
                f"Food Courts: {food_info}\n"
                f"Accessibility: {', '.join(venue.accessibility_services[:4])}\n"
                f"Transit: {venue.nearest_transit}"
            )

        match_ctx = "No live matches currently."
        if live_matches:
            m = live_matches[0]
            match_ctx = (
                f"LIVE: {m['home_team']['flag']} {m['home_team']['name']} {m['score']} "
                f"{m['away_team']['name']} {m['away_team']['flag']} at {m['venue_name']}"
            )

        result = ai_service.ask("fan", "fan_chat", {
            "venue_context": venue_ctx,
            "match_context": match_ctx,
            "user_input": message,
        })

        return {
            "reply": result.data.get("reply", ""),
            "suggestions": result.data.get("suggestions", []),
            "urgent": result.data.get("urgent", False),
            "ai_powered": True,
            "from_cache": result.from_cache,
            "fallback_used": result.fallback_used,
        }
