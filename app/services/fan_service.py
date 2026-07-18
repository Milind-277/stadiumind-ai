"""
app/services/fan_service.py — Business logic for the Fan persona.

This service implements all Fan Features:

    * **AI Match Assistant**      — :meth:`chat`
    * **Crowd Prediction**        — embedded in :meth:`get_wayfinding` via Decision Engine
    * **Route Recommendation**    — :meth:`get_wayfinding`
    * **Stadium Navigation**      — :meth:`get_wayfinding`, :meth:`get_venue_info`
    * **Emergency Alerts**        — urgent flag surfaced through :meth:`chat` and
                                    :meth:`get_wayfinding` from Decision Engine

The service composes :class:`~app.repositories.match_repo.MatchRepository`,
:class:`~app.repositories.venue_repo.VenueRepository`,
:class:`~app.repositories.crowd_repo.CrowdRepository`, and
:class:`~app.ai.decision_engine.DecisionEngine` to produce AI-enhanced,
JSON-serialisable responses.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai import ai_service
from app.ai.decision_engine import DecisionEngine
from app.constants import (
    INTENT_FAN_CHAT,
    NO_EMERGENCY_ACTION,
    ROLE_FAN,
)
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.utils.datetime_utils import format_match_time, time_until

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialize_team(team: Any) -> Dict[str, Any]:
    """Serialise a :class:`~app.models.match.Team` to a summary dict.

    Args:
        team: A ``Team`` dataclass instance.

    Returns:
        Dict with ``name``, ``code``, and ``flag`` keys.
    """
    return {
        "name": team.name,
        "code": team.code,
        "flag": team.flag_emoji,
    }


def _serialize_team_detail(team: Any) -> Dict[str, Any]:
    """Serialise a :class:`~app.models.match.Team` to a detail dict.

    Extends :func:`_serialize_team` with the ``group`` field used on the
    match-detail page.

    Args:
        team: A ``Team`` dataclass instance.

    Returns:
        Dict with ``name``, ``code``, ``flag``, and ``group`` keys.
    """
    return {**_serialize_team(team), "group": team.group}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FanService:
    """Fan-facing business logic for schedules, navigation, and AI chat.

    Attributes:
        matches:         Repository for match data.
        venues:          Repository for venue data.
        crowds:          Repository for live crowd snapshot data.
        decision_engine: Deterministic AI decision engine for fan recommendations.
    """

    def __init__(self, data_dir: str = "data") -> None:
        """Initialise JSON-backed repositories and the Decision Engine.

        Args:
            data_dir: Path to the directory containing JSON data files.
        """
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)
        self.crowds = CrowdRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_decision_support(
        self,
        venue_id: str,
        accessibility_needs: Optional[List[str]] = None,
        language: str = "English",
    ) -> Dict[str, Any]:
        """Build a JSON-serialisable Decision Support payload for fans.

        Delegates to :meth:`~app.ai.decision_engine.DecisionEngine.safe_decide`
        which always returns a valid dict even when venue data is missing.

        Args:
            venue_id:            Target venue identifier.
            accessibility_needs: Optional list of fan accessibility requirements.
            language:            Preferred language for recommendations.

        Returns:
            Decision support dict with gate, navigation, crowd-avoidance,
            emergency, accessibility, and transportation recommendations.
        """
        return self.decision_engine.safe_decide(
            user_role=ROLE_FAN,
            venue_id=venue_id,
            accessibility_needs=accessibility_needs,
            language=language,
        )

    def _is_emergency_active(self, decision_support: Dict[str, Any]) -> bool:
        """Return ``True`` when the decision support signals an active emergency.

        Args:
            decision_support: The dict returned by :meth:`_build_decision_support`.

        Returns:
            ``True`` if emergency actions are non-trivial, else ``False``.
        """
        return decision_support.get("emergency_actions", []) != [NO_EMERGENCY_ACTION]

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_all_matches(self) -> List[Dict[str, Any]]:
        """Return all matches with formatted display times and live status.

        Returns:
            List of match summary dicts suitable for the schedule and home pages.
        """
        return [
            {
                "id": m.id,
                "home_team": _serialize_team(m.home_team),
                "away_team": _serialize_team(m.away_team),
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
            for m in self.matches.find_all()
        ]

    def get_match_detail(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Return full match detail with venue information.

        Args:
            match_id: Unique match identifier (e.g. ``"m001"``).

        Returns:
            Full match detail dict, or ``None`` if the match is not found.
        """
        m = self.matches.find_by_id(match_id)
        if not m:
            return None
        venue = self.venues.find_by_id(m.venue_id)
        venue_detail: Dict[str, Any] = (
            {
                "name": venue.name,
                "city": venue.city,
                "country": venue.country,
                "nearest_transit": venue.nearest_transit,
            }
            if venue
            else {"name": m.venue_name}
        )
        return {
            "id": m.id,
            "home_team": _serialize_team_detail(m.home_team),
            "away_team": _serialize_team_detail(m.away_team),
            "venue": venue_detail,
            "kickoff_display": format_match_time(m.kickoff_utc),
            "stage": m.stage,
            "group": m.group,
            "status": m.status,
            "score": m.score_display,
            "attendance": m.attendance,
            "highlights": m.highlights,
        }

    def get_wayfinding(self, venue_id: str, destination: str) -> Dict[str, Any]:
        """Return AI-enhanced Route Recommendation and Stadium Navigation advice.

        Uses the Decision Engine to produce gate selection, crowd-avoidance
        guidance, and accessibility recommendations tailored to the venue's
        live crowd state.

        Args:
            venue_id:    Target venue identifier.
            destination: Fan-supplied destination name within the venue.

        Returns:
            Wayfinding dict with venue info, AI guidance, gate list, and
            accessibility services.  Returns ``{"error": "Venue not found"}``
            when the venue ID is invalid.
        """
        venue = self.venues.find_by_id(venue_id)
        if not venue:
            logger.warning("Fan wayfinding requested for missing venue_id=%s", venue_id)
            return {"error": "Venue not found"}

        decision_support = self._build_decision_support(
            venue_id=venue_id,
            accessibility_needs=["wayfinding"],
        )

        ai_guidance: Dict[str, Any] = {
            "reply": (
                f"Use {decision_support['best_gate']} to reach {destination}. "
                f"{decision_support['transportation_suggestion']}"
            ),
            "suggestions": (
                decision_support["navigation_advice"]
                + decision_support["crowd_avoidance"]
                + decision_support["accessibility_recommendations"]
            )[:5],
            "urgent": self._is_emergency_active(decision_support),
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

    def get_venue_info(self, venue_id: str) -> Optional[Dict[str, Any]]:
        """Return venue details for the fan portal including occupancy.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Venue detail dict including gates, food courts, and current
            occupancy percentage, or ``None`` if not found.
        """
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

    def chat(self, message: str, venue_id: str) -> Dict[str, Any]:
        """Process a fan message through the AI Match Assistant.

        Builds rich venue and match context then calls the AI pipeline.
        Falls back to Decision Engine guidance when AI is unavailable so the
        fan always receives a useful response.

        Args:
            message:  The fan's natural language question or request.
            venue_id: Venue context identifier for location-aware responses.

        Returns:
            Dict with ``reply``, ``suggestions``, ``urgent``, ``ai_powered``,
            ``from_cache``, ``fallback_used``, and ``decision_support`` fields.
        """
        venue = self.venues.find_by_id(venue_id) if venue_id else None
        matches = self.get_all_matches()
        live_matches = [m for m in matches if m["is_live"]]

        venue_ctx = self._build_venue_context_string(venue)
        match_ctx = self._build_match_context_string(live_matches)

        decision_support: Optional[Dict[str, Any]] = None
        if venue:
            decision_support = self._build_decision_support(venue_id=venue_id)

        try:
            result = ai_service.ask(
                ROLE_FAN,
                INTENT_FAN_CHAT,
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
            result_data, from_cache, fallback_used = self._chat_fallback(
                message, decision_support
            )

        return {
            "reply": result_data.get("reply", ""),
            "suggestions": result_data.get("suggestions", []),
            "urgent": result_data.get("urgent", False),
            "ai_powered": True,
            "from_cache": from_cache,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    # ── Private context builders ───────────────────────────────────────────────

    def _build_venue_context_string(self, venue: Any) -> str:
        """Build a compact venue context string for the AI prompt.

        Args:
            venue: A ``Venue`` model instance, or ``None``.

        Returns:
            A multi-line context string or a placeholder when no venue is set.
        """
        if not venue:
            return "No specific venue selected."
        food_info = ", ".join(f.name for f in venue.food_courts)
        gate_info = ", ".join(f"{g.name} ({g.location})" for g in venue.gates)
        return (
            f"Venue: {venue.name}, {venue.city}, {venue.country}\n"
            f"Capacity: {venue.capacity:,}\n"
            f"Gates: {gate_info}\n"
            f"Food Courts: {food_info}\n"
            f"Accessibility: {', '.join(venue.accessibility_services[:4])}\n"
            f"Transit: {venue.nearest_transit}"
        )

    def _build_match_context_string(self, live_matches: List[Dict[str, Any]]) -> str:
        """Build a live match context string for the AI prompt.

        Args:
            live_matches: List of live match summary dicts.

        Returns:
            A single-line match context string, or a placeholder if no live match.
        """
        if not live_matches:
            return "No live matches currently."
        m = live_matches[0]
        return (
            f"LIVE: {m['home_team']['flag']} {m['home_team']['name']} {m['score']} "
            f"{m['away_team']['name']} {m['away_team']['flag']} at {m['venue_name']}"
        )

    def _chat_fallback(
        self,
        message: str,
        decision_support: Optional[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], bool, bool]:
        """Build a structured fallback response when the AI pipeline fails.

        Args:
            message:          The original fan message.
            decision_support: Decision Engine payload, may be ``None``.

        Returns:
            A ``(result_data, from_cache, fallback_used)`` tuple.
        """
        if decision_support:
            reply = (
                f"{message} — use {decision_support['best_gate']} and follow the "
                "provided navigation guidance."
            )
            suggestions = (
                decision_support["navigation_advice"]
                + decision_support["crowd_avoidance"]
            )[:3]
            urgent = self._is_emergency_active(decision_support)
        else:
            reply = "Please visit an information booth near the main gates for assistance."
            suggestions = []
            urgent = False

        return (
            {"reply": reply, "suggestions": suggestions, "urgent": urgent},
            False,
            True,
        )
