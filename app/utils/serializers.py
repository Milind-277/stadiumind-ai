"""
app/utils/serializers.py — Shared serialisation helpers for domain models.

Centralises incident-to-dict serialization used across multiple services
to eliminate code duplication and ensure a consistent API contract.
"""

from typing import Any, Dict

# ── Severity sort order ────────────────────────────────────────────────────────
SEVERITY_ORDER: Dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

# ── Task priority sort order ───────────────────────────────────────────────────
PRIORITY_ORDER: Dict[str, int] = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def serialize_incident_summary(incident: Any) -> Dict[str, Any]:
    """
    Serialise an Incident model to a summary dict (organizer view).

    Returns a condensed representation used in dashboard and report endpoints.
    """
    return {
        "id": incident.id,
        "venue_id": incident.venue_id,
        "zone_name": incident.zone_name,
        "type": incident.type.value,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "description": incident.description,
        "reported_at": incident.reported_at,
        "is_active": incident.is_active,
    }


def serialize_incident_detail(incident: Any) -> Dict[str, Any]:
    """
    Serialise an Incident model to a full detail dict (security view).

    Returns the complete representation including AI fields, notes, and zone_id.
    """
    return {
        "id": incident.id,
        "venue_id": incident.venue_id,
        "zone_id": incident.zone_id,
        "zone_name": incident.zone_name,
        "type": incident.type.value,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "description": incident.description,
        "reported_by": incident.reported_by,
        "reported_at": incident.reported_at,
        "assigned_to": incident.assigned_to,
        "ai_classification": incident.ai_classification,
        "ai_recommendation": incident.ai_recommendation,
        "notes": incident.notes,
        "is_active": incident.is_active,
    }
