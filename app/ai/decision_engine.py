"""
app/ai/decision_engine.py — Deterministic Decision Engine for StadiumMind AI.

Responsibilities:
    * **Context Building**   — assemble live crowd, venue, match, incident, and
                               weather data into a structured :class:`DecisionContext`.
    * **Prompt Generation**  — convert a :class:`DecisionContext` into a Gemini-ready
                               structured prompt via :class:`PromptBuilder`.
    * **Decision Making**    — produce deterministic operational recommendations
                               (gate selection, crowd avoidance, navigation, emergency
                               actions, accessibility, transportation) without an AI call.
    * **Fallback Safety**    — :meth:`DecisionEngine.safe_decide` guarantees a valid
                               response even when venue data is unavailable.

This module is the single source of truth for operational decision logic and is
consumed by all four persona services.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.constants import (
    CROWD_CRITICAL_THRESHOLD,
    CROWD_CRITICAL_ZONE_COUNT,
    CROWD_HIGH_THRESHOLD,
    CROWD_MODERATE_THRESHOLD,
    FALLBACK_GATE_NAME,
    MAX_ACCESSIBILITY_ITEMS,
    MAX_ACCESSIBILITY_RECOMMENDATIONS,
    MAX_CROWD_AVOIDANCE_TIPS,
    NO_EMERGENCY_ACTION,
)

from app.models.crowd import DensityLevel
from app.models.incident import IncidentType, SeverityLevel
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository


@dataclass
class DecisionContext:
    """Structured operational context used by the decision engine."""

    user_role: str
    crowd_status: Dict[str, Any]
    venue: Dict[str, Any]
    match: Dict[str, Any]
    accessibility_needs: List[str]
    language: str
    weather: Dict[str, Any]
    emergency_status: Dict[str, Any]


class ContextBuilder:
    """Build a structured decision context from repository data."""

    def __init__(self, data_dir: str = "data") -> None:
        self.crowds = CrowdRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)

    def build(
        self,
        user_role: str,
        venue_id: str,
        match_id: Optional[str] = None,
        accessibility_needs: Optional[List[str]] = None,
        language: str = "English",
    ) -> DecisionContext:
        """Assemble the operational context used for decisions."""
        venue = self.venues.find_by_id(venue_id)
        if venue is None:
            raise ValueError(f"Venue not found: {venue_id}")

        match = self._resolve_match(venue_id, match_id)
        snapshot = self.crowds.find_latest_by_venue(venue_id)
        incidents = self.incidents.find_by_venue(venue_id)

        return DecisionContext(
            user_role=user_role,
            crowd_status=self._build_crowd_status(snapshot),
            venue=self._build_venue_context(venue),
            match=self._build_match_context(match),
            accessibility_needs=self._build_accessibility_needs(
                venue.accessibility_services,
                accessibility_needs or [],
            ),
            language=language,
            weather=self._build_weather_context(venue.city),
            emergency_status=self._build_emergency_status(incidents),
        )

    def _resolve_match(self, venue_id: str, match_id: Optional[str]) -> Any:
        """Return the target match for the venue."""
        if match_id:
            match = self.matches.find_by_id(match_id)
            if match is None:
                raise ValueError(f"Match not found: {match_id}")
            return match

        matches = self.matches.find_where(lambda m: m.venue_id == venue_id)
        live_match = next((match for match in matches if match.is_live), None)
        if live_match is not None:
            return live_match
        if matches:
            return sorted(matches, key=lambda match: match.kickoff_utc)[0]
        raise ValueError(f"Match not found for venue: {venue_id}")

    def _build_crowd_status(self, snapshot: Any) -> Dict[str, Any]:
        """Convert a crowd snapshot into structured status data."""
        if snapshot is None:
            return {
                "available": False,
                "severity": "unknown",
                "occupancy_pct": 0.0,
                "bottleneck_zones": [],
                "high_density_zones": [],
            }

        high_density_zones = [
            {
                "zone_id": zone.zone_id,
                "zone_name": zone.zone_name,
                "occupancy_pct": zone.occupancy_pct,
                "density_level": zone.density_level.value,
            }
            for zone in snapshot.zones
            if zone.density_level in (DensityLevel.HIGH, DensityLevel.CRITICAL)
        ]
        severity = self._derive_crowd_severity(
            snapshot.overall_occupancy_pct,
            high_density_zones,
        )
        return {
            "available": True,
            "severity": severity,
            "timestamp": snapshot.timestamp,
            "occupancy_pct": snapshot.overall_occupancy_pct,
            "attendance": snapshot.total_attendance,
            "capacity": snapshot.venue_capacity,
            "bottleneck_zones": snapshot.bottleneck_zones,
            "high_density_zones": high_density_zones,
            "alert_active": snapshot.alert_active,
        }

    def _build_venue_context(self, venue: Any) -> Dict[str, Any]:
        """Convert a venue model into structured decision data."""
        return {
            "id": venue.id,
            "name": venue.name,
            "city": venue.city,
            "country": venue.country,
            "capacity": venue.capacity,
            "nearest_transit": venue.nearest_transit,
            "gates": [
                {
                    "id": gate.id,
                    "name": gate.name,
                    "location": gate.location,
                    "accessible": gate.accessible,
                    "open_time": gate.open_time,
                }
                for gate in venue.gates
            ],
            "zones": [
                {
                    "id": zone.id,
                    "name": zone.name,
                    "type": zone.type,
                    "capacity": zone.capacity,
                    "level": zone.level,
                    "accessible": zone.accessible,
                }
                for zone in venue.zones
            ],
            "accessibility_services": venue.accessibility_services,
        }

    def _build_match_context(self, match: Any) -> Dict[str, Any]:
        """Convert a match model into structured decision data."""
        return {
            "id": match.id,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "venue_name": match.venue_name,
            "kickoff_utc": match.kickoff_utc,
            "stage": match.stage,
            "status": match.status,
            "attendance": match.attendance,
            "highlights": match.highlights,
        }

    def _build_accessibility_needs(
        self,
        venue_services: Iterable[str],
        user_needs: Iterable[str],
    ) -> List[str]:
        """Merge venue accessibility services with user-reported needs.

        Args:
            venue_services: Services offered by the venue.
            user_needs:     Specific needs reported by the requesting user.

        Returns:
            De-duplicated list capped at :data:`~app.constants.MAX_ACCESSIBILITY_ITEMS`.
        """
        merged = list(dict.fromkeys([*venue_services, *user_needs]))
        return merged[:MAX_ACCESSIBILITY_ITEMS]

    def _build_weather_context(self, city: str) -> Dict[str, Any]:
        """Return deterministic mock weather for the venue city."""
        city_key = city.lower()
        if "vancouver" in city_key:
            return {
                "condition": "light_rain",
                "temperature_c": 18,
                "wind_kph": 12,
                "precipitation_chance": 55,
            }
        if "mexico" in city_key:
            return {
                "condition": "clear",
                "temperature_c": 24,
                "wind_kph": 8,
                "precipitation_chance": 10,
            }
        return {
            "condition": "partly_cloudy",
            "temperature_c": 21,
            "wind_kph": 10,
            "precipitation_chance": 20,
        }

    def _build_emergency_status(self, incidents: Iterable[Any]) -> Dict[str, Any]:
        """Summarise active emergency conditions from incidents."""
        active_incidents = [incident for incident in incidents if incident.is_active]
        emergency_incidents = [
            incident
            for incident in active_incidents
            if incident.type
            in {
                IncidentType.MEDICAL,
                IncidentType.FIRE_ALARM,
                IncidentType.SUSPICIOUS_ITEM,
                IncidentType.UNAUTHORIZED_ACCESS,
                IncidentType.FIGHT,
                IncidentType.STRUCTURAL,
            }
        ]
        highest_severity = self._highest_incident_severity(emergency_incidents)
        return {
            "active": bool(emergency_incidents),
            "level": highest_severity,
            "count": len(emergency_incidents),
            "zones": [incident.zone_name for incident in emergency_incidents],
            "types": [incident.type.value for incident in emergency_incidents],
        }

    def _derive_crowd_severity(
        self,
        occupancy_pct: float,
        high_density_zones: List[Dict[str, Any]],
    ) -> str:
        """Map crowd load to a simple operational severity label.

        Uses :data:`~app.constants.CROWD_CRITICAL_THRESHOLD`,
        :data:`~app.constants.CROWD_HIGH_THRESHOLD`, and
        :data:`~app.constants.CROWD_MODERATE_THRESHOLD`.

        Args:
            occupancy_pct:      Overall venue occupancy percentage.
            high_density_zones: List of zones with high or critical density.

        Returns:
            One of ``"critical"``, ``"high"``, ``"moderate"``, or ``"low"``.
        """
        if occupancy_pct >= CROWD_CRITICAL_THRESHOLD or len(high_density_zones) >= CROWD_CRITICAL_ZONE_COUNT:
            return "critical"
        if occupancy_pct >= CROWD_HIGH_THRESHOLD or high_density_zones:
            return "high"
        if occupancy_pct >= CROWD_MODERATE_THRESHOLD:
            return "moderate"
        return "low"

    def _highest_incident_severity(self, incidents: List[Any]) -> str:
        """Return the highest severity label among incidents."""
        severity_rank = {
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4,
        }
        highest = SeverityLevel.LOW
        for incident in incidents:
            if severity_rank.get(incident.severity, 0) > severity_rank.get(highest, 0):
                highest = incident.severity
        return highest.value


class PromptBuilder:
    """Generate a Gemini-ready structured prompt for decision support."""

    def build(self, context: DecisionContext) -> str:
        """Return a structured prompt for Gemini."""
        return (
            "You are StadiumMind Decision Engine, a backend operations assistant.\n"
            "Use the provided context to generate operational recommendations only.\n\n"
            f"USER ROLE: {context.user_role}\n"
            f"LANGUAGE: {context.language}\n"
            f"VENUE: {context.venue['name']} ({context.venue['city']}, {context.venue['country']})\n"
            f"MATCH: {context.match['home_team']} vs {context.match['away_team']}\n"
            f"CROWD STATUS: {context.crowd_status}\n"
            f"ACCESSIBILITY NEEDS: {context.accessibility_needs}\n"
            f"WEATHER: {context.weather}\n"
            f"EMERGENCY STATUS: {context.emergency_status}\n\n"
            "INSTRUCTIONS:\n"
            "1. Recommend the best gate.\n"
            "2. Provide navigation advice.\n"
            "3. Provide crowd avoidance guidance.\n"
            "4. Provide emergency actions if needed.\n"
            "5. Provide accessibility recommendations.\n"
            "6. Suggest transportation based on venue context and weather.\n\n"
            "Respond ONLY with valid JSON matching this exact schema:\n"
            "{\n"
            '  "best_gate": "string",\n'
            '  "navigation_advice": ["string"],\n'
            '  "crowd_avoidance": ["string"],\n'
            '  "emergency_actions": ["string"],\n'
            '  "accessibility_recommendations": ["string"],\n'
            '  "transportation_suggestion": "string"\n'
            "}"
        )


class DecisionEngine:
    """Deterministic decision engine for operational recommendations."""

    def __init__(self, data_dir: str = "data") -> None:
        self.context_builder = ContextBuilder(data_dir)
        self.prompt_builder = PromptBuilder()

    def build_context(
        self,
        user_role: str,
        venue_id: str,
        match_id: Optional[str] = None,
        accessibility_needs: Optional[List[str]] = None,
        language: str = "English",
    ) -> DecisionContext:
        """Build the structured operational context."""
        return self.context_builder.build(
            user_role=user_role,
            venue_id=venue_id,
            match_id=match_id,
            accessibility_needs=accessibility_needs,
            language=language,
        )

    def build_prompt(self, context: DecisionContext) -> str:
        """Generate the Gemini prompt for the given context."""
        return self.prompt_builder.build(context)

    def safe_decide(
        self,
        user_role: str,
        venue_id: str,
        accessibility_needs: Optional[List[str]] = None,
        language: str = "English",
        fallback_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build context and decide, guaranteeing a valid response on failure.

        This method is the single safe entry point for all persona services.
        It never raises — any exception is caught, logged, and replaced with a
        structured fallback that can be overridden per-persona.

        Args:
            user_role:           Persona role (``"fan"``, ``"organizer"``, etc.).
            venue_id:            Target venue identifier.
            accessibility_needs: Optional list of accessibility requirements.
            language:            Preferred language for recommendations.
            fallback_overrides:  Optional dict merged into the fallback response
                                 to supply persona-specific default values.

        Returns:
            Decision support dict with gate, navigation, crowd-avoidance,
            emergency, accessibility, and transportation recommendations.
        """
        _log = logging.getLogger(__name__)
        try:
            context = self.build_context(
                user_role=user_role,
                venue_id=venue_id,
                accessibility_needs=accessibility_needs or [],
                language=language,
            )
            decision = self.decide(context)
            _log.info(
                "Decision support built for %s service venue_id=%s best_gate=%s",
                user_role,
                venue_id,
                decision.get("best_gate"),
            )
            return decision
        except Exception as exc:
            _log.exception(
                "Decision support fallback for %s service venue_id=%s",
                user_role,
                venue_id,
            )
            fallback: Dict[str, Any] = {
                "best_gate": FALLBACK_GATE_NAME,
                "navigation_advice": ["Follow on-site signage and staff directions."],
                "crowd_avoidance": [
                    "Avoid the busiest concourses during peak movement."
                ],
                "emergency_actions": [NO_EMERGENCY_ACTION],
                "accessibility_recommendations": [
                    "Request help from venue staff if needed."
                ],
                "transportation_suggestion": (
                    "Use public transit or the venue's nearest transport option."
                ),
                "error": str(exc),
            }
            if fallback_overrides:
                fallback.update(fallback_overrides)
            return fallback

    def decide(self, context: DecisionContext) -> Dict[str, Any]:
        """Return deterministic operational recommendations from context."""
        venue = context.venue
        crowd_status = context.crowd_status
        emergency_status = context.emergency_status
        weather = context.weather

        best_gate = self._select_best_gate(
            venue, context.accessibility_needs, crowd_status
        )
        navigation_advice = self._build_navigation_advice(
            best_gate, crowd_status, weather
        )
        crowd_avoidance = self._build_crowd_avoidance(crowd_status, venue)
        emergency_actions = self._build_emergency_actions(emergency_status)
        accessibility_recommendations = self._build_accessibility_recommendations(
            context.accessibility_needs,
            venue,
            best_gate,
        )
        transportation_suggestion = self._build_transportation_suggestion(
            venue, weather
        )

        return {
            "best_gate": best_gate,
            "navigation_advice": navigation_advice,
            "crowd_avoidance": crowd_avoidance,
            "emergency_actions": emergency_actions,
            "accessibility_recommendations": accessibility_recommendations,
            "transportation_suggestion": transportation_suggestion,
        }

    def _select_best_gate(
        self,
        venue: Dict[str, Any],
        accessibility_needs: List[str],
        crowd_status: Dict[str, Any],
    ) -> str:
        """Pick the most suitable gate based on accessibility needs and congestion.

        Selection priority:
            1. Accessible gate (when accessibility needs are present).
            2. Gate furthest from known bottleneck zones.
            3. First accessible gate.
            4. First gate in the venue list.
            5. :data:`~app.constants.FALLBACK_GATE_NAME` when no gate data exists.

        Args:
            venue:               Venue context dict.
            accessibility_needs: List of active accessibility requirements.
            crowd_status:        Current crowd status dict.

        Returns:
            Gate name string.
        """
        gates = venue.get("gates", [])
        accessible_gates = [gate for gate in gates if gate.get("accessible")]
        if accessibility_needs and accessible_gates:
            return accessible_gates[0]["name"]

        bottlenecks = set(crowd_status.get("bottleneck_zones", []))
        if bottlenecks:
            preferred = self._gate_away_from_bottlenecks(gates, bottlenecks)
            if preferred is not None:
                return preferred["name"]

        if accessible_gates:
            return accessible_gates[0]["name"]
        return gates[0]["name"] if gates else FALLBACK_GATE_NAME

    def _gate_away_from_bottlenecks(
        self,
        gates: List[Dict[str, Any]],
        bottlenecks: Iterable[str],
    ) -> Optional[Dict[str, Any]]:
        """Return a gate that avoids likely bottleneck directions."""
        bottleneck_text = " ".join(bottlenecks).lower()
        for gate in gates:
            location = gate.get("location", "").lower()
            if location and location not in bottleneck_text:
                return gate
        return gates[0] if gates else None

    def _build_navigation_advice(
        self,
        best_gate: str,
        crowd_status: Dict[str, Any],
        weather: Dict[str, Any],
    ) -> List[str]:
        """Build step-by-step navigation advice."""
        advice = [f"Enter via {best_gate}."]
        if crowd_status.get("severity") in {"high", "critical"}:
            advice.append(
                "Follow staff directions and avoid the busiest concourse areas."
            )
        if weather.get("condition") in {"light_rain", "rain", "storm"}:
            advice.append("Allow extra time for slower movement due to weather.")
        advice.append("Use indoor routes where possible to stay clear of congestion.")
        return advice

    def _build_crowd_avoidance(
        self,
        crowd_status: Dict[str, Any],
        venue: Dict[str, Any],
    ) -> List[str]:
        """Recommend zones and crowd patterns to avoid.

        Args:
            crowd_status: Current crowd status dict.
            venue:        Venue context dict.

        Returns:
            List of crowd-avoidance tips capped at
            :data:`~app.constants.MAX_CROWD_AVOIDANCE_TIPS`.
        """
        avoidance: List[str] = []
        for zone in crowd_status.get("high_density_zones", []):
            avoidance.append(f"Avoid {zone['zone_name']} if possible.")
        for bottleneck in crowd_status.get("bottleneck_zones", []):
            avoidance.append(f"Avoid the area linked to bottleneck zone {bottleneck}.")
        if not avoidance:
            avoidance.append(
                f"Avoid the busiest concourses at {venue['name']} during peak movement periods."
            )
        return avoidance[:MAX_CROWD_AVOIDANCE_TIPS]

    def _build_emergency_actions(self, emergency_status: Dict[str, Any]) -> List[str]:
        """Recommend emergency actions based on active incident status.

        Args:
            emergency_status: Emergency status dict from :class:`ContextBuilder`.

        Returns:
            List of emergency action strings.
        """
        if not emergency_status.get("active"):
            return [NO_EMERGENCY_ACTION]
        actions = ["Follow venue emergency staff instructions immediately."]
        actions.append("Move away from the affected area and keep access routes clear.")
        if emergency_status.get("level") in {"high", "critical"}:
            actions.append("Escalate to security and medical response teams now.")
        return actions

    def _build_accessibility_recommendations(
        self,
        accessibility_needs: List[str],
        venue: Dict[str, Any],
        best_gate: str,
    ) -> List[str]:
        """Translate accessibility needs into practical venue guidance.

        Args:
            accessibility_needs: List of active accessibility requirements.
            venue:               Venue context dict.
            best_gate:           Previously selected optimal gate.

        Returns:
            List of accessibility recommendations capped at
            :data:`~app.constants.MAX_ACCESSIBILITY_RECOMMENDATIONS`.
        """
        recommendations = [
            f"Use {best_gate}, which is the preferred accessible entry point."
        ]
        if accessibility_needs:
            recommendations.append(
                f"Ask staff for support related to: {', '.join(accessibility_needs[:3])}."
            )
        recommendations.append(
            "Keep a copy of venue accessibility services handy while moving."
        )
        if venue.get("accessibility_services"):
            recommendations.append(
                "Use the venue's accessibility services if assistance is needed."
            )
        return recommendations[:MAX_ACCESSIBILITY_RECOMMENDATIONS]

    def _build_transportation_suggestion(
        self,
        venue: Dict[str, Any],
        weather: Dict[str, Any],
    ) -> str:
        """Recommend a transport option using the venue and weather data."""
        transit = venue.get("nearest_transit") or "public transit"
        if weather.get("condition") in {"light_rain", "rain", "storm"}:
            return (
                f"Use {transit} and plan for extra walking time because of the weather."
            )
        return f"Use {transit} for the most direct and reliable arrival route."


def build_decision_context(
    user_role: str,
    venue_id: str,
    match_id: Optional[str] = None,
    accessibility_needs: Optional[List[str]] = None,
    language: str = "English",
    data_dir: str = "data",
) -> DecisionContext:
    """Build and return a decision context using JSON-backed data."""
    engine = DecisionEngine(data_dir=data_dir)
    return engine.build_context(
        user_role=user_role,
        venue_id=venue_id,
        match_id=match_id,
        accessibility_needs=accessibility_needs,
        language=language,
    )


def build_decision_prompt(context: DecisionContext, data_dir: str = "data") -> str:
    """Build a Gemini-ready prompt for the given decision context."""
    engine = DecisionEngine(data_dir=data_dir)
    return engine.build_prompt(context)


def recommend_actions(
    user_role: str,
    venue_id: str,
    match_id: Optional[str] = None,
    accessibility_needs: Optional[List[str]] = None,
    language: str = "English",
    data_dir: str = "data",
) -> Dict[str, Any]:
    """Return Phase 3 decision recommendations using only backend data."""
    engine = DecisionEngine(data_dir=data_dir)
    context = engine.build_context(
        user_role=user_role,
        venue_id=venue_id,
        match_id=match_id,
        accessibility_needs=accessibility_needs,
        language=language,
    )
    return engine.decide(context)
