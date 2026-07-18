"""
app/constants.py — Project-wide named constants.

Centralises every magic number, hardcoded string, and repeated literal so that
the rest of the codebase references one authoritative definition.  Changing a
value here propagates everywhere automatically.

Do NOT import Flask or any application module from this file — it must be safe
to import at any point in the boot process (including before ``create_app``).
"""

# ---------------------------------------------------------------------------
# Persona / Role identifiers
# ---------------------------------------------------------------------------

#: All valid user-facing roles accepted by the role-selector and role guard.
ROLE_FAN = "fan"
ROLE_ORGANIZER = "organizer"
ROLE_VOLUNTEER = "volunteer"
ROLE_SECURITY = "security"

#: Frozen set of all valid roles — used by middleware and session handling.
ALL_ROLES: frozenset = frozenset(
    {ROLE_FAN, ROLE_ORGANIZER, ROLE_VOLUNTEER, ROLE_SECURITY}
)

# ---------------------------------------------------------------------------
# Default venue
# ---------------------------------------------------------------------------

#: Venue ID used when no ``venue_id`` query parameter is supplied by the client.
DEFAULT_VENUE_ID = "v001"

# ---------------------------------------------------------------------------
# Demo identifiers
# ---------------------------------------------------------------------------

#: Volunteer used as the "logged-in" volunteer for demo / prototype mode.
DEMO_VOLUNTEER_ID = "vol001"

# ---------------------------------------------------------------------------
# Crowd occupancy thresholds  (percentage points, inclusive lower bound)
# ---------------------------------------------------------------------------

#: Occupancy at or above this value → "critical" crowd severity.
CROWD_CRITICAL_THRESHOLD: int = 90

#: Occupancy at or above this value → "high" crowd severity.
CROWD_HIGH_THRESHOLD: int = 75

#: Occupancy at or above this value → "moderate" crowd severity.
CROWD_MODERATE_THRESHOLD: int = 50

#: Minimum number of high-density zones that trigger "critical" crowd severity.
CROWD_CRITICAL_ZONE_COUNT: int = 2

# ---------------------------------------------------------------------------
# Real-time simulation
# ---------------------------------------------------------------------------

#: Maximum percentage jitter applied to zone crowd counts in live-feed endpoints.
CROWD_JITTER_PCT: float = 0.02

# ---------------------------------------------------------------------------
# AI pipeline intent identifiers
# ---------------------------------------------------------------------------

INTENT_FAN_CHAT = "fan_chat"
INTENT_CROWD_ANALYSIS = "crowd_analysis"
INTENT_INCIDENT_CLASSIFY = "incident_classify"
INTENT_VOLUNTEER_GUIDANCE = "volunteer_guidance"
INTENT_EVENT_BRIEFING = "event_briefing"

# ---------------------------------------------------------------------------
# Incident defaults
# ---------------------------------------------------------------------------

#: Default incident type assigned at creation before AI classification.
INCIDENT_DEFAULT_TYPE = "unclassified"

#: Default severity assigned to new incidents logged via the Security blueprint.
INCIDENT_DEFAULT_SEVERITY = "medium"

#: Default severity assigned to SOS escalations submitted by volunteers.
SOS_DEFAULT_SEVERITY = "high"

#: Status value written to the incident record when it is resolved.
INCIDENT_RESOLVED_STATUS = "resolved"

#: Prefix added to descriptions of incidents created via volunteer SOS.
SOS_DESCRIPTION_PREFIX = "[SOS ESCALATION] "

# ---------------------------------------------------------------------------
# Incident ID prefixes
# ---------------------------------------------------------------------------

#: ID prefix for incidents created by the Security team.
INCIDENT_ID_PREFIX = "inc_"

#: ID prefix for incidents created via a volunteer SOS escalation.
SOS_INCIDENT_ID_PREFIX = "inc_sos_"

#: ID prefix for broadcast alert records.
ALERT_ID_PREFIX = "alrt_"

# ---------------------------------------------------------------------------
# Incident field update allow-list (Security blueprint PATCH)
# ---------------------------------------------------------------------------

#: Fields that the Security persona is permitted to update on an existing incident.
INCIDENT_UPDATE_FIELDS: frozenset = frozenset({"status", "assigned_to", "notes"})

# ---------------------------------------------------------------------------
# Decision engine fallback values
# ---------------------------------------------------------------------------

#: Fallback gate name used when no venue data is available.
FALLBACK_GATE_NAME = "Main gate"

#: Placeholder message used in decision-support fallbacks.
NO_EMERGENCY_ACTION = "No immediate emergency action required."

# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------

#: Maximum number of accessibility items surfaced to the decision engine.
MAX_ACCESSIBILITY_ITEMS: int = 10

#: Maximum number of crowd-avoidance tips returned by the decision engine.
MAX_CROWD_AVOIDANCE_TIPS: int = 4

#: Maximum number of accessibility recommendations returned.
MAX_ACCESSIBILITY_RECOMMENDATIONS: int = 4

# ---------------------------------------------------------------------------
# API / Serialisation limits
# ---------------------------------------------------------------------------

#: Maximum length of an incident description excerpt in AI classification output.
AI_CLASSIFICATION_DESC_LIMIT: int = 200

#: Maximum number of incidents surfaced in the event-briefing prompt.
BRIEFING_MAX_ACTIVE_INCIDENTS: int = 5

#: Maximum number of volunteer accessibility items in a decision-support build.
VOLUNTEER_MAX_ACCESSIBILITY_ITEMS: int = 3

# ---------------------------------------------------------------------------
# Logging format
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# ---------------------------------------------------------------------------
# HTTP status codes (symbolic aliases for readability)
# ---------------------------------------------------------------------------

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

#: Session key that stores the active persona role.
SESSION_ROLE_KEY = "role"

# ---------------------------------------------------------------------------
# Volunteer status values
# ---------------------------------------------------------------------------

VOLUNTEER_STATUS_AVAILABLE = "available"
VOLUNTEER_STATUS_BUSY = "busy"
VOLUNTEER_STATUS_OFF_DUTY = "off_duty"

# ---------------------------------------------------------------------------
# Task completion status (used for timestamp injection)
# ---------------------------------------------------------------------------

TASK_STATUS_COMPLETED = "completed"

# ---------------------------------------------------------------------------
# Content-Security-Policy
# ---------------------------------------------------------------------------

CSP_VALUE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self';"
)
