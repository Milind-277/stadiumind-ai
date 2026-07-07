"""
app/ai/prompt_manager.py — Versioned prompt template loader and safe injector.

Security: User content is ALWAYS placed inside a <user_input> XML tag.
This prevents prompt injection attacks by clearly delineating untrusted input
from the system instruction in the prompt.
"""
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Intent → template file name mapping
INTENT_TEMPLATE_MAP: Dict[str, str] = {
    "fan_chat": "fan_assistant.txt",
    "crowd_analysis": "crowd_analysis.txt",
    "incident_classify": "incident_classifier.txt",
    "volunteer_guidance": "volunteer_guidance.txt",
    "event_briefing": "event_briefing.txt",
}

_template_cache: Dict[str, str] = {}


def _load_template(filename: str) -> str:
    """Load and cache a prompt template from disk."""
    if filename not in _template_cache:
        path = os.path.join(PROMPTS_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt template not found: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            _template_cache[filename] = fh.read()
        logger.debug("Loaded prompt template: %s", filename)
    return _template_cache[filename]


def build(intent: str, context: Dict[str, Any]) -> str:
    """
    Load a prompt template by intent and safely inject context variables.

    Context keys map to {{KEY}} placeholders in the template.
    User-provided text must be passed under the key 'user_input' —
    it will be automatically sandboxed inside <user_input> XML tags.

    Args:
        intent: One of the keys in INTENT_TEMPLATE_MAP
        context: Dict of template variable values

    Returns:
        The fully composed prompt string, ready to send to Gemini.

    Raises:
        KeyError: If intent is not recognised.
        FileNotFoundError: If template file is missing.
    """
    if intent not in INTENT_TEMPLATE_MAP:
        raise KeyError(f"Unknown AI intent: '{intent}'. Valid: {list(INTENT_TEMPLATE_MAP)}")

    template = _load_template(INTENT_TEMPLATE_MAP[intent])

    # Sandbox user content — NEVER inject user text directly into the template body
    user_content = context.pop("user_input", "")
    safe_context = {k: str(v)[:2000] for k, v in context.items()}  # truncate context values

    # Replace {{KEY}} placeholders
    prompt = template
    for key, value in safe_context.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)

    # Append sandboxed user input at the end
    if user_content:
        prompt += f"\n\n<user_input>\n{user_content[:500]}\n</user_input>"

    logger.debug("Built prompt for intent=%s, length=%d chars", intent, len(prompt))
    return prompt
