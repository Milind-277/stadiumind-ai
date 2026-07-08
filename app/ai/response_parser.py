"""
app/ai/response_parser.py — AI response validation and type coercion.

Each intent has an expected output schema. If the AI response doesn't match,
this module raises AIOutputInvalidError so the caller can use a fallback.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AIOutputInvalidError(Exception):
    """Raised when AI response doesn't match expected schema."""


# Minimum required keys per intent
REQUIRED_KEYS: Dict[str, list] = {
    "fan_chat": ["reply", "suggestions"],
    "crowd_analysis": ["summary", "severity", "recommendations"],
    "incident_classify": ["type", "severity", "recommendation"],
    "volunteer_guidance": ["guidance", "steps"],
    "event_briefing": ["title", "summary", "key_points", "action_items"],
}


def parse(intent: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate AI output dict against the expected schema for the given intent.

    Returns the raw dict if valid (possibly with type-coerced fields).
    Raises AIOutputInvalidError if schema is violated.
    """
    if not isinstance(raw, dict):
        raise AIOutputInvalidError(f"Expected dict, got {type(raw).__name__}")

    required = REQUIRED_KEYS.get(intent, [])
    missing = [k for k in required if k not in raw]
    if missing:
        raise AIOutputInvalidError(
            f"AI response for intent='{intent}' missing keys: {missing}"
        )

    # Coerce: ensure all string fields are actually strings
    for key in required:
        if key in raw and not isinstance(raw[key], (str, list, dict)):
            raw[key] = str(raw[key])

    # Ensure suggestions/steps/recommendations are always lists
    for list_key in (
        "suggestions",
        "steps",
        "recommendations",
        "key_points",
        "action_items",
    ):
        if list_key in raw and not isinstance(raw[list_key], list):
            raw[list_key] = [str(raw[list_key])]

    logger.debug("AI response validated for intent=%s", intent)
    return raw
