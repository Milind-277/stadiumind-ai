"""
app/services/organizer_service.py — Business logic for the Organizer persona.

This service implements all Organizer Features:

    * **AI Resource Allocation** — :meth:`get_ai_crowd_analysis`
    * **Incident Monitoring**    — :meth:`get_all_incidents`
    * **Venue Analytics**        — :meth:`get_live_crowd`
    * **Match Dashboard**        — :meth:`get_dashboard_summary`
    * **AI Recommendations**     — :meth:`generate_event_briefing`

Plus cross-cutting:
    * **Emergency Alerts**       — :meth:`broadcast_alert`

The service composes repositories for crowd, incident, volunteer, match, and
venue data, together with :class:`~app.ai.decision_engine.DecisionEngine`
for deterministic AI recommendations.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from app.ai import ai_service
from app.ai.decision_engine import DecisionEngine
from app.constants import (
    ALERT_ID_PREFIX,
    BRIEFING_MAX_ACTIVE_INCIDENTS,
    CROWD_CRITICAL_THRESHOLD,
    CROWD_HIGH_THRESHOLD,
    CROWD_JITTER_PCT,
    INTENT_CROWD_ANALYSIS,
    INTENT_EVENT_BRIEFING,
    ROLE_ORGANIZER,
)
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.repositories.volunteer_repo import TaskRepository, VolunteerRepository
from app.utils.datetime_utils import utcnow_iso
from app.utils.serializers import SEVERITY_ORDER, serialize_incident_summary

logger = logging.getLogger(__name__)


class OrganizerService:
    """Organizer-facing business logic for real-time operations and reporting.

    Attributes:
        crowds:          Repository for live crowd snapshot data.
        incidents:       Repository for security incidents.
        volunteers:      Repository for volunteer profiles.
        tasks:           Repository for volunteer tasks.
        matches:         Repository for match schedules.
        venues:          Repository for venue information.
        decision_engine: Deterministic AI decision engine for organizer recommendations.
    """

    def __init__(self, data_dir: str = "data") -> None:
        """Initialise repositories and the Decision Engine.

        Args:
            data_dir: Path to the directory containing JSON data files.
        """
        self.crowds = CrowdRepository(data_dir)
        self.incidents = IncidentRepository(data_dir)
        self.volunteers = VolunteerRepository(data_dir)
        self.tasks = TaskRepository(data_dir)
        self.matches = MatchRepository(data_dir)
        self.venues = VenueRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_decision_support(self, venue_id: str) -> Dict[str, Any]:
        """Build a JSON-serialisable Decision Support payload for organizers.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Decision support dict with gate, navigation, crowd-avoidance,
            emergency, accessibility, and transportation recommendations.
        """
        return self.decision_engine.safe_decide(
            user_role=ROLE_ORGANIZER,
            venue_id=venue_id,
            fallback_overrides={
                "navigation_advice": ["Review live venue signage and traffic flows."],
                "crowd_avoidance": ["Avoid bottleneck areas until density improves."],
                "accessibility_recommendations": [
                    "Confirm accessible routes with venue staff."
                ],
                "transportation_suggestion": "Use the venue's nearest transit option.",
            },
        )

    @staticmethod
    def _derive_fallback_severity(occupancy_pct: float) -> str:
        """Map occupancy percentage to a severity label for AI fallbacks.

        Args:
            occupancy_pct: Venue-wide occupancy as a percentage (0–100).

        Returns:
            One of ``"critical"``, ``"high"``, or ``"moderate"``.
        """
        if occupancy_pct >= CROWD_CRITICAL_THRESHOLD:
            return "critical"
        if occupancy_pct >= CROWD_HIGH_THRESHOLD:
            return "high"
        return "moderate"

    @staticmethod
    def _apply_jitter(zone: Any) -> int:
        """Apply ±:data:`~app.constants.CROWD_JITTER_PCT` random jitter to a zone count.

        Simulates real-time crowd fluctuation for the live-feed endpoint.

        Args:
            zone: A ``ZoneDensity`` model instance.

        Returns:
            A jitter-adjusted count clamped to ``[0, zone.capacity]``.
        """
        max_jitter = int(zone.capacity * CROWD_JITTER_PCT)
        jitter = random.randint(-max_jitter, max_jitter)
        return max(0, min(zone.capacity, zone.current_count + jitter))

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Return aggregated Match Dashboard data for all active venues.

        Collects live crowd snapshots, active incident counts, volunteer
        availability, and live match state across every venue.

        Returns:
            Summary dict with incident counts, volunteer stats, live match
            count, per-venue occupancy, and a top-level alert flag.
        """
        all_incidents = self.incidents.find_all()
        active_incidents = [i for i in all_incidents if i.is_active]
        critical = [i for i in active_incidents if i.severity.value == "critical"]
        all_volunteers = self.volunteers.find_all()
        available_vols = [v for v in all_volunteers if v.status == "available"]
        live_matches = [m for m in self.matches.find_all() if m.status == "live"]

        venue_summaries = self._build_venue_summaries()

        return {
            "total_active_incidents": len(active_incidents),
            "critical_incidents": len(critical),
            "total_volunteers": len(all_volunteers),
            "available_volunteers": len(available_vols),
            "live_matches": len(live_matches),
            "venues": venue_summaries,
            "alert_active": any(v["alert_active"] for v in venue_summaries),
        }

    def _build_venue_summaries(self) -> List[Dict[str, Any]]:
        """Collect the latest crowd snapshot for each venue.

        Returns:
            List of venue summary dicts for venues that have crowd data.
        """
        venue_summaries = []
        for venue in self.venues.find_all():
            snapshot = self.crowds.find_latest_by_venue(venue.id)
            if snapshot:
                venue_summaries.append(
                    {
                        "venue_id": venue.id,
                        "venue_name": venue.name,
                        "city": venue.city,
                        "attendance": snapshot.total_attendance,
                        "capacity": snapshot.venue_capacity,
                        "occupancy_pct": snapshot.overall_occupancy_pct,
                        "alert_active": snapshot.alert_active,
                        "bottleneck_count": len(snapshot.bottleneck_zones),
                    }
                )
        return venue_summaries

    def get_live_crowd(self, venue_id: Optional[str] = None) -> Dict[str, Any]:
        """Return live Venue Analytics crowd data with simulated real-time jitter.

        Applies ±:data:`~app.constants.CROWD_JITTER_PCT` random fluctuation to
        each zone count to simulate real-time changes without a persistent IoT feed.

        Args:
            venue_id: Optional venue filter; omit to return data for all venues.

        Returns:
            Dict with a ``venues`` list, each containing per-zone crowd state.
        """
        snapshots = self._collect_snapshots(venue_id)
        return {"venues": [self._serialize_snapshot(snap) for snap in snapshots]}

    def _collect_snapshots(self, venue_id: Optional[str]) -> list:
        """Collect the relevant crowd snapshots.

        Args:
            venue_id: If supplied, returns only that venue's snapshot.

        Returns:
            List of ``CrowdSnapshot`` model instances.
        """
        if venue_id:
            snapshot = self.crowds.find_latest_by_venue(venue_id)
            return [snapshot] if snapshot else []
        return [
            s
            for venue in self.venues.find_all()
            if (s := self.crowds.find_latest_by_venue(venue.id)) is not None
        ]

    def _serialize_snapshot(self, snap: Any) -> Dict[str, Any]:
        """Serialise a CrowdSnapshot with jitter-adjusted zone counts.

        Args:
            snap: A ``CrowdSnapshot`` model instance.

        Returns:
            Dict with venue-level and zone-level crowd data.
        """
        zones_data = [
            {
                "zone_id": z.zone_id,
                "zone_name": z.zone_name,
                "current_count": (simulated := self._apply_jitter(z)),
                "capacity": z.capacity,
                "occupancy_pct": (
                    round((simulated / z.capacity) * 100, 1) if z.capacity else 0
                ),
                "density_level": z.density_level.value,
            }
            for z in snap.zones
        ]
        return {
            "venue_id": snap.venue_id,
            "timestamp": utcnow_iso(),
            "total_attendance": snap.total_attendance,
            "venue_capacity": snap.venue_capacity,
            "occupancy_pct": snap.overall_occupancy_pct,
            "alert_active": snap.alert_active,
            "bottleneck_zones": snap.bottleneck_zones,
            "zones": zones_data,
        }

    def get_ai_crowd_analysis(self, venue_id: str) -> Dict[str, Any]:
        """Return AI Resource Allocation crowd analysis for a venue.

        Calls the AI pipeline with live zone density data and returns
        AI-generated severity assessment and crowd management recommendations.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Dict with venue name, AI analysis payload, and Decision Support.
            Returns ``{"error": "..."}`` when venue or crowd data is missing.
        """
        snapshot = self.crowds.find_latest_by_venue(venue_id)
        venue = self.venues.find_by_id(venue_id)
        if not snapshot or not venue:
            logger.warning(
                "Crowd analysis requested for missing venue_id=%s", venue_id
            )
            return {"error": "Venue or crowd data not found"}

        decision_support = self._build_decision_support(venue_id)
        zone_text = self._build_zone_text(snapshot)
        bottleneck_text = ", ".join(snapshot.bottleneck_zones) or "None"

        try:
            result = ai_service.ask(
                ROLE_ORGANIZER,
                INTENT_CROWD_ANALYSIS,
                {
                    "venue_name": venue.name,
                    "timestamp": snapshot.timestamp,
                    "total_attendance": str(snapshot.total_attendance),
                    "venue_capacity": str(snapshot.venue_capacity),
                    "occupancy_pct": str(snapshot.overall_occupancy_pct),
                    "zone_data": zone_text,
                    "bottleneck_zones": bottleneck_text,
                },
            )
            analysis = result.data
            from_cache = result.from_cache
            fallback_used = result.fallback_used
        except Exception:
            logger.exception(
                "Organizer crowd analysis AI fallback venue_id=%s", venue_id
            )
            analysis, from_cache, fallback_used = self._crowd_analysis_fallback(
                venue, snapshot, decision_support
            )

        return {
            "venue_name": venue.name,
            "analysis": analysis,
            "ai_powered": True,
            "from_cache": from_cache,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    @staticmethod
    def _build_zone_text(snapshot: Any) -> str:
        """Build a human-readable zone density summary for the AI prompt.

        Args:
            snapshot: A ``CrowdSnapshot`` model instance.

        Returns:
            Multi-line string with one zone per line.
        """
        return "\n".join(
            f"- {z.zone_name}: {z.current_count}/{z.capacity} ({z.occupancy_pct}%) — {z.density_level.value}"
            for z in snapshot.zones
        )

    def _crowd_analysis_fallback(
        self,
        venue: Any,
        snapshot: Any,
        decision_support: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool, bool]:
        """Build a structured crowd analysis fallback when the AI pipeline fails.

        Args:
            venue:            Venue model instance.
            snapshot:         Latest crowd snapshot.
            decision_support: Decision Engine payload.

        Returns:
            ``(analysis, from_cache, fallback_used)`` tuple.
        """
        severity = self._derive_fallback_severity(snapshot.overall_occupancy_pct)
        analysis = {
            "summary": (
                f"{venue.name} is at {snapshot.overall_occupancy_pct}% occupancy "
                "with live crowd decision support enabled."
            ),
            "severity": severity,
            "critical_zones": snapshot.bottleneck_zones[:2],
            "recommendations": decision_support["navigation_advice"][:3],
            "prediction": "Monitor bottlenecks and adjust flow guidance in real time.",
            "alert_message": None,
        }
        return analysis, False, True

    def generate_event_briefing(self, venue_id: str) -> Dict[str, Any]:
        """Generate an AI Recommendations operational briefing for a venue.

        Aggregates crowd, incident, volunteer, and match state then calls the
        AI pipeline to produce a structured operational report.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Dict with venue name, AI briefing payload, and Decision Support.
            Returns ``{"error": "Venue not found"}`` when venue ID is invalid.
        """
        venue = self.venues.find_by_id(venue_id)
        if not venue:
            logger.warning(
                "Event briefing requested for missing venue_id=%s", venue_id
            )
            return {"error": "Venue not found"}

        snapshot = self.crowds.find_latest_by_venue(venue_id)
        incidents = self.incidents.find_by_venue(venue_id)
        active_incidents = [i for i in incidents if i.is_active]
        volunteers = self.volunteers.find_where(lambda v: v.venue_id == venue_id)
        matches = self.matches.find_where(lambda m: m.venue_id == venue_id)
        live_match = next((m for m in matches if m.status == "live"), None)
        decision_support = self._build_decision_support(venue_id)

        context = self._build_briefing_context(
            venue, snapshot, active_incidents, volunteers, live_match
        )

        try:
            result = ai_service.ask(ROLE_ORGANIZER, INTENT_EVENT_BRIEFING, context)
            briefing = result.data
            from_cache = result.from_cache
            fallback_used = result.fallback_used
        except Exception:
            logger.exception("Organizer briefing AI fallback venue_id=%s", venue_id)
            briefing, from_cache, fallback_used = self._briefing_fallback(
                venue, active_incidents, context["crowd_summary"], context["volunteer_summary"],
                decision_support
            )

        return {
            "venue_name": venue.name,
            "briefing": briefing,
            "ai_powered": True,
            "from_cache": from_cache,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    def _build_briefing_context(
        self,
        venue: Any,
        snapshot: Any,
        active_incidents: list,
        volunteers: list,
        live_match: Any,
    ) -> Dict[str, Any]:
        """Assemble the AI prompt context dict for the event briefing.

        Args:
            venue:            Venue model instance.
            snapshot:         Latest crowd snapshot (may be ``None``).
            active_incidents: List of active incident models.
            volunteers:       List of volunteer models at this venue.
            live_match:       The currently live match, or ``None``.

        Returns:
            Context dict suitable for passing to :func:`~app.ai.ai_service.ask`.
        """
        match_summary = (
            f"{live_match.home_team.name} vs {live_match.away_team.name} (LIVE)"
            if live_match
            else "No live match"
        )
        crowd_summary = (
            f"Attendance: {snapshot.total_attendance:,}/{snapshot.venue_capacity:,} "
            f"({snapshot.overall_occupancy_pct}%)"
            if snapshot
            else "N/A"
        )
        incident_summary = (
            "\n".join(
                f"- [{i.severity.value.upper()}] {i.type.value}: {i.description[:80]}"
                for i in active_incidents[:BRIEFING_MAX_ACTIVE_INCIDENTS]
            )
            or "No active incidents"
        )
        available_count = sum(1 for v in volunteers if v.status == "available")
        vol_summary = f"{len(volunteers)} deployed, {available_count} available"

        return {
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
        }

    @staticmethod
    def _briefing_fallback(
        venue: Any,
        active_incidents: list,
        crowd_summary: str,
        vol_summary: str,
        decision_support: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool, bool]:
        """Build a structured event briefing fallback when the AI pipeline fails.

        Args:
            venue:            Venue model instance.
            active_incidents: List of currently active incidents.
            crowd_summary:    Pre-built crowd summary string.
            vol_summary:      Pre-built volunteer summary string.
            decision_support: Decision Engine payload.

        Returns:
            ``(briefing, from_cache, fallback_used)`` tuple.
        """
        briefing = {
            "title": f"Operational Briefing — {venue.name}",
            "summary": (
                f"{venue.name} is operational with {len(active_incidents)} active "
                "incidents and decision support active for the current venue state."
            ),
            "key_points": [
                crowd_summary,
                f"Active incidents: {len(active_incidents)}",
                f"Volunteers: {vol_summary}",
            ],
            "priorities": decision_support["crowd_avoidance"][:3],
            "action_items": decision_support["navigation_advice"][:3],
            "positive_indicators": ["Live decision support available"],
            "overall_status": "yellow",
        }
        return briefing, False, True

    def broadcast_alert(
        self, title: str, message: str, priority: str, venue_id: str
    ) -> Dict[str, Any]:
        """Create and broadcast an Emergency Alert record.

        Args:
            title:    Alert headline.
            message:  Alert body text.
            priority: Alert priority level (e.g. ``"critical"``, ``"high"``).
            venue_id: Target venue identifier.

        Returns:
            Dict with the created ``alert`` record and a ``broadcast`` flag.
        """
        now = utcnow_iso()
        alert_id = f"{ALERT_ID_PREFIX}{now.replace(':', '').replace('-', '')[:14]}"
        alert = {
            "id": alert_id,
            "title": title,
            "message": message,
            "priority": priority,
            "venue_id": venue_id,
            "created_at": now,
            "created_by": ROLE_ORGANIZER,
        }
        logger.info("Alert broadcast: %s — %s", priority.upper(), title)
        return {"alert": alert, "broadcast": True}

    def get_all_incidents(self) -> List[Dict[str, Any]]:
        """Return all incidents for Incident Monitoring, sorted by severity.

        Returns:
            List of incident summary dicts sorted critical-first then chronologically.
        """
        incidents = self.incidents.find_all()
        incidents.sort(
            key=lambda i: (SEVERITY_ORDER.get(i.severity.value, 9), i.reported_at),
        )
        return [serialize_incident_summary(i) for i in incidents]
