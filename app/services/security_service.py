"""app/services/security_service.py — Business logic for the Security persona."""
import logging
from typing import Any, Dict, List, Optional

from app.repositories.incident_repo import IncidentRepository
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.venue_repo import VenueRepository
from app.models.incident import IncidentType, SeverityLevel, IncidentStatus
from app.utils.datetime_utils import utcnow_iso
from app.ai import ai_service

logger = logging.getLogger(__name__)

# Emergency protocols lookup (in real world → database table)
PROTOCOLS = {
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
        "resources": ["Crowd control officers", "PA operator", "Digital signage team", "Medical standby"],
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
        "resources": ["First-aid volunteers", "AED device", "Emergency services", "Medical bay"],
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


class SecurityService:
    def __init__(self, data_dir: str = "data"):
        self.incidents = IncidentRepository(data_dir)
        self.crowds = CrowdRepository(data_dir)
        self.venues = VenueRepository(data_dir)

    def get_all_incidents(self, venue_id: str = None) -> List[Dict]:
        """Return all incidents, optionally filtered by venue."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        if venue_id:
            all_incidents = self.incidents.find_by_venue(venue_id)
        else:
            all_incidents = self.incidents.find_all()
        all_incidents.sort(key=lambda i: (not i.is_active, severity_order.get(i.severity.value, 9)))
        return [
            {
                "id": i.id,
                "venue_id": i.venue_id,
                "zone_id": i.zone_id,
                "zone_name": i.zone_name,
                "type": i.type.value,
                "severity": i.severity.value,
                "status": i.status.value,
                "description": i.description,
                "reported_by": i.reported_by,
                "reported_at": i.reported_at,
                "assigned_to": i.assigned_to,
                "ai_classification": i.ai_classification,
                "ai_recommendation": i.ai_recommendation,
                "notes": i.notes,
                "is_active": i.is_active,
            }
            for i in all_incidents
        ]

    def log_incident(self, venue_id: str, zone_id: str, zone_name: str,
                     description: str, reported_by: str = "security") -> Dict:
        """Log a new security incident."""
        incident_data = {
            "id": f"inc_{utcnow_iso().replace(':', '').replace('-', '').replace('+', '')[:14]}",
            "venue_id": venue_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "type": "unclassified",
            "severity": "medium",
            "status": "open",
            "description": description,
            "reported_by": reported_by,
            "reported_at": utcnow_iso(),
            "notes": [],
        }
        saved = self.incidents.save(incident_data)
        logger.info("New incident logged: %s in %s", incident_data["id"], zone_name)
        return {
            "id": incident_data["id"],
            "status": "open",
            "message": "Incident logged. Use AI classify to get response recommendations.",
        }

    def update_incident(self, incident_id: str, data: Dict) -> Optional[Dict]:
        """Update an incident's status or fields."""
        if "status" in data and data["status"] == "resolved":
            data["resolved_at"] = utcnow_iso()
        updated = self.incidents.update(incident_id, data)
        if not updated:
            return None
        return {"id": updated.id, "status": updated.status.value}

    def classify_incident(self, incident_id: str) -> Dict:
        """Use AI to classify an incident and generate response recommendation."""
        incident = self.incidents.find_by_id(incident_id)
        if not incident:
            return {"error": "Incident not found"}

        venue = self.venues.find_by_id(incident.venue_id)
        venue_name = venue.name if venue else incident.venue_id

        result = ai_service.ask("security", "incident_classify", {
            "venue_name": venue_name,
            "zone_name": incident.zone_name,
            "reported_at": incident.reported_at,
            "user_input": incident.description,
        })

        classification = result.data.get("type", "unclassified")
        recommendation = result.data.get("recommendation", "")
        severity = result.data.get("severity", incident.severity.value)

        # Persist AI classification back to incident
        self.incidents.update(incident_id, {
            "ai_classification": f"{classification.upper()} — {severity.upper()} severity. {recommendation[:200]}",
            "ai_recommendation": "\n".join(result.data.get("steps", [])),
            "type": classification,
            "severity": severity,
        })

        return {
            "incident_id": incident_id,
            "classification": result.data,
            "ai_powered": True,
            "fallback_used": result.fallback_used,
        }

    def get_zone_heatmap(self, venue_id: str) -> Dict:
        """Return zone density heatmap data for a venue."""
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

    def get_protocol(self, incident_type: str) -> Dict:
        """Return emergency protocol for an incident type."""
        protocol = PROTOCOLS.get(incident_type)
        if not protocol:
            return {
                "name": "General Response Protocol",
                "steps": [
                    "Assess the situation via CCTV and radio reports",
                    "Dispatch nearest available security officer",
                    "Escalate to supervisor if situation cannot be contained",
                    "Document all actions and timestamps",
                ],
                "resources": ["Security officer", "Zone supervisor"],
            }
        return protocol
