"""app/services/fan_service.py — Business logic for the Fan persona."""

import logging
from typing import Dict, List, Optional

from app.ai import ai_service
from app.ai.decision_engine import DecisionEngine
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.utils.datetime_utils import format_match_time, time_until

logger = logging.getLogger(__name__)


class FanService:
    """Fan-facing business logic for schedules, wayfinding, and chat."""

    def __init__(self, data_dir: str = "data"):
        """Initialise JSON-backed repositories and the decision engine."""
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)
        self.crowds = CrowdRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    def _build_decision_support(
        self,
        venue_id: str,
        accessibility_needs: Optional[List[str]] = None,
        language: str = "English",
    ) -> Dict:
        """Build a JSON-serializable decision support payload for fans."""
        return self.decision_engine.safe_decide(
            user_role="fan",
            venue_id=venue_id,
            accessibility_needs=accessibility_needs,
            language=language,
        )

    def get_all_matches(self) -> List[Dict]:
        """Return all matches with formatted times and status."""
        result = []
        for m in self.matches.find_all():
            result.append(
                {
                    "id": m.id,
                    "home_team": {
                        "name": m.home_team.name,
                        "code": m.home_team.code,
                        "flag": m.home_team.flag_emoji,
                    },
                    "away_team": {
                        "name": m.away_team.name,
                        "code": m.away_team.code,
                        "flag": m.away_team.flag_emoji,
                    },
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
                }
            )
        return result

    def get_match_detail(self, match_id: str) -> Optional[Dict]:
        """Return full match detail with venue info."""
        m = self.matches.find_by_id(match_id)
        if not m:
            return None
        venue = self.venues.find_by_id(m.venue_id)
        return {
            "id": m.id,
            "home_team": {
                "name": m.home_team.name,
                "code": m.home_team.code,
                "flag": m.home_team.flag_emoji,
                "group": m.home_team.group,
            },
            "away_team": {
                "name": m.away_team.name,
                "code": m.away_team.code,
                "flag": m.away_team.flag_emoji,
                "group": m.away_team.group,
            },
            "venue": (
                {
                    "name": venue.name if venue else m.venue_name,
                    "city": venue.city if venue else "",
                    "country": venue.country if venue else "",
                    "nearest_transit": venue.nearest_transit if venue else "",
                }
                if venue
                else {"name": m.venue_name}
            ),
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
            logger.warning("Fan wayfinding requested for missing venue_id=%s", venue_id)
            return {"error": "Venue not found"}

        decision_support = self._build_decision_support(
            venue_id=venue_id,
            accessibility_needs=["wayfinding"],
        )

        ai_guidance = {
            "reply": (
                f"Use {decision_support['best_gate']} to reach {destination}. "
                f"{decision_support['transportation_suggestion']}"
            ),
            "suggestions": (
                decision_support["navigation_advice"]
                + decision_support["crowd_avoidance"]
                + decision_support["accessibility_recommendations"]
            )[:5],
            "urgent": decision_support["emergency_actions"]
            != ["No immediate emergency action required."],
            "decision_support": decision_support,
        }

        return {
            "venue_name": venue.name,
            "destination": destination,
            "ai_guidance": ai_guidance,
            "ai_powered": True,
            "fallback_used": False,
            "gates": [
                {"name": g.name, "location": g.location, "accessible": g.accessible}
                for g in venue.gates
            ],
            "accessibility_services": venue.accessibility_services,
            "decision_support": decision_support,
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
            "gates": [
                {
                    "id": g.id,
                    "name": g.name,
                    "location": g.location,
                    "accessible": g.accessible,
                    "open_time": g.open_time,
                }
                for g in venue.gates
            ],
            "food_courts": [
                {
                    "id": f.id,
                    "name": f.name,
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

        decision_support = None
        if venue:
            decision_support = self._build_decision_support(venue_id=venue_id)

        try:
            result = ai_service.ask(
                "fan",
                "fan_chat",
                {
                    "venue_context": venue_ctx,
                    "match_context": match_ctx,
                    "user_input": message,
                },
            )
            result_data = result.data
            from_cache = result.from_cache
            fallback_used = result.fallback_used
        except Exception:
            logger.exception("Fan chat AI fallback venue_id=%s", venue_id)
            result_data = {
                "reply": (
                    f"{message} - use {decision_support['best_gate']} and follow the "
                    "provided navigation guidance."
                ),
                "suggestions": (
                    decision_support["navigation_advice"]
                    + decision_support["crowd_avoidance"]
                )[:3],
                "urgent": decision_support["emergency_actions"]
                != ["No immediate emergency action required."],
            }
            from_cache = False
            fallback_used = True

        return {
            "reply": result_data.get("reply", ""),
            "suggestions": result_data.get("suggestions", []),
            "urgent": result_data.get("urgent", False),
            "ai_powered": True,
            "from_cache": from_cache,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }
