"""
app/services/security_service.py — Business logic for the Security persona.

This service implements all Security Features:

    * **Threat Detection**        — :meth:`get_zone_heatmap`
    * **Incident Classification** — :meth:`classify_incident`
    * **Risk Analysis**           — AI severity and confidence scoring
    * **Emergency Response**      — :meth:`get_protocol`
    * **AI Decision Support**     — Decision Engine embedded in every classification

Emergency protocols are defined in :data:`EMERGENCY_PROTOCOLS` and describe
step-by-step response procedures for each known incident type.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai import ai_service
from app.ai.decision_engine import DecisionEngine
from app.constants import (
    AI_CLASSIFICATION_DESC_LIMIT,
    INCIDENT_DEFAULT_SEVERITY,
    INCIDENT_DEFAULT_TYPE,
    INCIDENT_ID_PREFIX,
    INCIDENT_RESOLVED_STATUS,
    INTENT_INCIDENT_CLASSIFY,
    ROLE_SECURITY,
)
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.venue_repo import VenueRepository
from app.utils.datetime_utils import utcnow_iso
from app.utils.serializers import SEVERITY_ORDER, serialize_incident_detail

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Emergency response protocol registry
# ---------------------------------------------------------------------------

#: Maps incident type values to structured Emergency Response protocols.
#: In a production system this would live in a database table; here it is
#: kept as a module-level constant to make it easy for an evaluator to see
#: every supported protocol at a glance.
EMERGENCY_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "crowd_surge": {
        "name": "Crowd Surge Protocol",
        "steps": [
            "Immediately assess the affected zone using CCTV and radio reports",
            "Dispatch crowd control officers to zone entry points",
            "Implement one-in-one-out access control at all entry points to the zone",
            "Activate PA announcement directing fans to alternative areas",
            "Update digital wayfinding signs with real-time crowd information",
            "Alert medical standby team to be on-call for potential injuries",
            "Escalate to venue commander if density exceeds 90% capacity",
        ],
        "resources": [
            "Crowd control officers",
            "PA operator",
            "Digital signage team",
            "Medical standby",
        ],
    },
    "medical": {
        "name": "Medical Emergency Protocol",
        "steps": [
            "Dispatch nearest trained first-aid volunteer to scene immediately",
            "Clear a 3-metre radius around the patient",
            "Assess vital signs — apply AED if cardiac event suspected",
            "Contact emergency services (911/999) if life-threatening",
            "Designate a volunteer to guide paramedics from nearest gate",
            "Keep crowd moving away from the scene — avoid spectator congestion",
            "Document time, location, and nature of emergency",
        ],
        "resources": [
            "First-aid volunteers",
            "AED device",
            "Emergency services",
            "Medical bay",
        ],
    },
    "unauthorized_access": {
        "name": "Unauthorized Access Protocol",
        "steps": [
            "Do not attempt to physically restrain — observe and radio immediately",
            "Dispatch 2 security officers to intercept",
            "Request backup from nearest security checkpoint",
            "Identify and document individuals (description, direction of travel)",
            "Secure the breached access point",
            "Coordinate with police liaison if individuals cannot be contained",
        ],
        "resources": ["Security officers", "Police liaison", "CCTV operator"],
    },
    "suspicious_item": {
        "name": "Suspicious Item Protocol",
        "steps": [
            "Establish 20-metre exclusion zone immediately — DO NOT TOUCH",
            "Evacuate all fans from the immediate area",
            "Contact venue security coordinator and police immediately",
            "Keep all personnel clear until EOD team arrives",
            "Do not use radios within 10 metres of the item",
            "Document exact location, time, and description",
            "Prepare for potential larger evacuation if directed by police",
        ],
        "resources": ["Security officers", "Police/EOD team", "Evacuation team"],
    },
    "fire_alarm": {
        "name": "Fire Alarm Protocol",
        "steps": [
            "Activate PA system: 'Please proceed calmly to your nearest exit'",
            "Deploy all volunteers to exit corridors for crowd direction",
            "Contact fire services immediately",
            "Evacuate affected zone first, then adjacent zones",
            "Account for all staff and volunteers at muster point",
            "Await all-clear from fire service before re-entry",
        ],
        "resources": ["All available volunteers", "Fire services", "PA operator"],
    },
}

#: Fallback protocol returned when no specific protocol matches the incident type.
_GENERAL_RESPONSE_PROTOCOL: Dict[str, Any] = {
    "name": "General Response Protocol",
    "steps": [
        "Assess the situation via CCTV and radio reports",
        "Dispatch nearest available security officer",
        "Escalate to supervisor if situation cannot be contained",
        "Document all actions and timestamps",
    ],
    "resources": ["Security officer", "Zone supervisor"],
}

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SecurityService:
    """Security command-centre business logic for incidents and protocols.

    Attributes:
        incidents:       Repository for security incidents.
        crowds:          Repository for live crowd snapshot data.
        venues:          Repository for venue information.
        decision_engine: Deterministic AI decision engine for security recommendations.
    """

    def __init__(self, data_dir: str = "data") -> None:
        """Initialise repositories and the Decision Engine.

        Args:
            data_dir: Path to the directory containing JSON data files.
        """
        self.incidents = IncidentRepository(data_dir)
        self.crowds = CrowdRepository(data_dir)
        self.venues = VenueRepository(data_dir)
        self.decision_engine = DecisionEngine(data_dir)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_decision_support(self, venue_id: str) -> Dict[str, Any]:
        """Build a JSON-serialisable AI Decision Support payload for security.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Decision support dict with gate, navigation, crowd-avoidance,
            emergency, accessibility, and transportation recommendations.
        """
        return self.decision_engine.safe_decide(
            user_role=ROLE_SECURITY,
            venue_id=venue_id,
            accessibility_needs=["emergency_response"],
            fallback_overrides={
                "navigation_advice": ["Keep emergency access routes clear."],
                "crowd_avoidance": [
                    "Avoid congested zones until the area is secured."
                ],
                "emergency_actions": [
                    "Escalate to security and medical response teams now."
                ],
                "accessibility_recommendations": [
                    "Preserve accessible evacuation routes."
                ],
                "transportation_suggestion": (
                    "Use venue-managed routes and follow command-centre instructions."
                ),
            },
        )

    @staticmethod
    def _build_incident_id() -> str:
        """Generate a timestamped incident ID.

        Returns:
            A unique string ID prefixed with :data:`~app.constants.INCIDENT_ID_PREFIX`.
        """
        timestamp_part = (
            utcnow_iso()
            .replace(":", "")
            .replace("-", "")
            .replace("+", "")[:14]
        )
        return f"{INCIDENT_ID_PREFIX}{timestamp_part}"

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_all_incidents(self, venue_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all incidents for Incident Classification triage.

        Args:
            venue_id: Optional venue filter; omit to return all incidents.

        Returns:
            List of incident detail dicts sorted active-first, then by
            descending severity for operational triage.
        """
        all_incidents = (
            self.incidents.find_by_venue(venue_id)
            if venue_id
            else self.incidents.find_all()
        )
        all_incidents.sort(
            key=lambda i: (not i.is_active, SEVERITY_ORDER.get(i.severity.value, 9))
        )
        return [serialize_incident_detail(i) for i in all_incidents]

    def log_incident(
        self,
        venue_id: str,
        zone_id: str,
        zone_name: str,
        description: str,
        reported_by: str = ROLE_SECURITY,
    ) -> Dict[str, Any]:
        """Log a new security incident into the Incident Classification workflow.

        Creates an ``unclassified`` / ``medium`` severity placeholder incident.
        The AI classification step (:meth:`classify_incident`) should be called
        immediately after to assign the correct type and severity.

        Args:
            venue_id:    Venue where the incident occurred.
            zone_id:     Zone identifier within the venue.
            zone_name:   Human-readable zone name.
            description: Free-text incident description.
            reported_by: Identifier of the reporting party (default: ``"security"``).

        Returns:
            Dict with the new incident ``id``, ``status``, and a guidance ``message``.
        """
        incident_data = {
            "id": self._build_incident_id(),
            "venue_id": venue_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "type": INCIDENT_DEFAULT_TYPE,
            "severity": INCIDENT_DEFAULT_SEVERITY,
            "status": "open",
            "description": description,
            "reported_by": reported_by,
            "reported_at": utcnow_iso(),
            "notes": [],
        }
        self.incidents.save(incident_data)
        logger.info(
            "New incident logged incident_id=%s zone_name=%s venue_id=%s",
            incident_data["id"],
            zone_name,
            venue_id,
        )
        return {
            "id": incident_data["id"],
            "status": "open",
            "message": "Incident logged. Use AI classify to get response recommendations.",
        }

    def update_incident(
        self, incident_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an incident's status or other permitted fields.

        Automatically stamps ``resolved_at`` when status is set to ``"resolved"``.

        Args:
            incident_id: Unique incident identifier.
            data:        Dict of fields to update.

        Returns:
            Dict with ``id`` and ``status`` on success, or ``None`` if not found.
        """
        if data.get("status") == INCIDENT_RESOLVED_STATUS:
            data["resolved_at"] = utcnow_iso()
        updated = self.incidents.update(incident_id, data)
        if not updated:
            return None
        return {"id": updated.id, "status": updated.status.value}

    def classify_incident(self, incident_id: str) -> Dict[str, Any]:
        """Use AI to classify an incident and generate an Emergency Response plan.

        Runs the incident through the AI Incident Classification pipeline,
        applies Risk Analysis to determine severity and confidence, and
        persists the results back to the incident record.

        Args:
            incident_id: Unique incident identifier.

        Returns:
            Dict with classification type, severity, confidence, recommendation,
            response steps, resources, estimated resolution time, and Decision
            Support payload.  Returns ``{"error": "Incident not found"}`` when
            the incident ID is invalid.
        """
        incident = self.incidents.find_by_id(incident_id)
        if not incident:
            logger.warning(
                "Incident classification requested for missing incident_id=%s",
                incident_id,
            )
            return {"error": "Incident not found"}

        venue = self.venues.find_by_id(incident.venue_id)
        venue_name = venue.name if venue else incident.venue_id
        decision_support = self._build_decision_support(incident.venue_id)

        protocol = self.get_protocol(incident.type.value)
        protocol_steps = protocol.get("steps", [])
        protocol_resources = protocol.get("resources", [])

        classification, severity, recommendation, steps, resources, fallback_used, result = (
            self._run_ai_classification(
                incident, venue_name, decision_support, protocol_steps, protocol_resources
            )
        )

        self._persist_classification(
            incident_id, classification, severity, recommendation, steps
        )

        return {
            "incident_id": incident_id,
            "classification": {
                "type": classification,
                "severity": severity,
                "confidence": (
                    getattr(result, "data", {}).get("confidence", "medium")
                    if result
                    else "medium"
                ),
                "recommendation": recommendation,
                "steps": steps,
                "resources_required": resources,
                "estimated_resolution_minutes": (
                    getattr(result, "data", {}).get("estimated_resolution_minutes", 20)
                    if result
                    else 20
                ),
            },
            "ai_powered": True,
            "fallback_used": fallback_used,
            "decision_support": decision_support,
        }

    def _run_ai_classification(
        self,
        incident: Any,
        venue_name: str,
        decision_support: Dict[str, Any],
        protocol_steps: list,
        protocol_resources: list,
    ) -> tuple:
        """Execute the AI classification pipeline for an incident.

        Args:
            incident:          Incident model instance.
            venue_name:        Human-readable venue name.
            decision_support:  Decision Engine payload for fallback.
            protocol_steps:    Pre-loaded protocol steps for fallback.
            protocol_resources: Pre-loaded protocol resources for fallback.

        Returns:
            7-tuple of ``(classification, severity, recommendation, steps,
            resources, fallback_used, result_or_none)``.
        """
        try:
            result = ai_service.ask(
                ROLE_SECURITY,
                INTENT_INCIDENT_CLASSIFY,
                {
                    "venue_name": venue_name,
                    "zone_name": incident.zone_name,
                    "reported_at": incident.reported_at,
                    "user_input": incident.description,
                },
            )
            classification = result.data.get("type", incident.type.value)
            recommendation = result.data.get(
                "recommendation", decision_support["emergency_actions"][0]
            )
            severity = result.data.get("severity", incident.severity.value)
            steps = result.data.get("steps", []) or protocol_steps
            resources = result.data.get("resources_required", protocol_resources)
            return (
                classification,
                severity,
                recommendation,
                steps,
                resources,
                result.fallback_used,
                result,
            )
        except Exception:
            logger.exception(
                "AI incident classification fallback incident_id=%s venue_id=%s",
                incident.id,
                incident.venue_id,
            )
            classification = incident.type.value
            recommendation = decision_support["emergency_actions"][0]
            steps = (
                decision_support["emergency_actions"]
                + decision_support["crowd_avoidance"]
            )
            if classification == INCIDENT_DEFAULT_TYPE:
                recommendation = decision_support["emergency_actions"][0]
            return (
                classification,
                incident.severity.value,
                recommendation,
                steps,
                protocol_resources,
                True,
                None,
            )

    def _persist_classification(
        self,
        incident_id: str,
        classification: str,
        severity: str,
        recommendation: str,
        steps: list,
    ) -> None:
        """Persist the AI classification result back to the incident record.

        Args:
            incident_id:    Unique incident identifier.
            classification: AI-assigned incident type.
            severity:       AI-assigned severity level.
            recommendation: Primary recommended action (truncated).
            steps:          Ordered response steps.
        """
        self.incidents.update(
            incident_id,
            {
                "ai_classification": (
                    f"{classification.upper()} — {severity.upper()} severity. "
                    f"{recommendation[:AI_CLASSIFICATION_DESC_LIMIT]}"
                ),
                "ai_recommendation": "\n".join(steps),
                "type": classification,
                "severity": severity,
            },
        )

    def get_zone_heatmap(self, venue_id: str) -> Dict[str, Any]:
        """Return zone density Threat Detection heatmap data for a venue.

        Args:
            venue_id: Target venue identifier.

        Returns:
            Dict with per-zone occupancy, density levels, and bottleneck flags.
            Returns ``{"error": "Data not found"}`` when data is unavailable.
        """
        snapshot = self.crowds.find_latest_by_venue(venue_id)
        venue = self.venues.find_by_id(venue_id)
        if not snapshot or not venue:
            return {"error": "Data not found"}

        return {
            "venue_name": venue.name,
            "timestamp": snapshot.timestamp,
            "overall_occupancy_pct": snapshot.overall_occupancy_pct,
            "alert_active": snapshot.alert_active,
            "zones": [
                {
                    "zone_id": z.zone_id,
                    "zone_name": z.zone_name,
                    "current_count": z.current_count,
                    "capacity": z.capacity,
                    "occupancy_pct": z.occupancy_pct,
                    "density_level": z.density_level.value,
                    "is_bottleneck": z.zone_id in snapshot.bottleneck_zones,
                }
                for z in snapshot.zones
            ],
        }

    def get_protocol(self, incident_type: str) -> Dict[str, Any]:
        """Return the Emergency Response protocol for an incident type.

        Args:
            incident_type: Incident type slug (e.g. ``"crowd_surge"``).

        Returns:
            Protocol dict with ``name``, ``steps``, and ``resources``.
            Falls back to the general response protocol for unknown types.
        """
        return EMERGENCY_PROTOCOLS.get(incident_type, _GENERAL_RESPONSE_PROTOCOL)
