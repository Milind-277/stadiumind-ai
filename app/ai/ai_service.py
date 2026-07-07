"""
app/ai/ai_service.py — Central AI Orchestrator.

Single entry point for all AI-powered features across all personas.
Handles: cache lookup → prompt building → Gemini call → parse → fallback.

Usage:
    result = ai_service.ask("fan", "fan_chat", {
        "user_input": "Where is the nearest food court?",
        "venue_context": "...",
        "match_context": "...",
    })
"""
import dataclasses
import logging
from typing import Any, Dict, Optional

from app.config import Config
from app.ai import cache, prompt_manager
from app.ai.gemini_client import GeminiClient, GeminiAPIError
from app.ai.response_parser import parse, AIOutputInvalidError

logger = logging.getLogger(__name__)

# Singleton Gemini client (lazy-initialised on first real call)
_gemini: Optional[GeminiClient] = None


def _get_gemini() -> GeminiClient:
    global _gemini
    if _gemini is None:
        _gemini = GeminiClient(
            api_key=Config.GEMINI_API_KEY,
            model=Config.AI_MODEL,
            max_tokens=Config.AI_MAX_TOKENS,
        )
    return _gemini


# ── Fallback Responses ─────────────────────────────────────────────────────────
# Every AI feature has a pre-written fallback. AI enhances; it never blocks.

FALLBACKS: Dict[str, Dict[str, Any]] = {
    "fan_chat": {
        "reply": "I'm here to help! For the quickest assistance, please visit one of our information booths near the main gates — our staff will be happy to answer your question.",
        "suggestions": [
            "Visit the information booth near Gate A or Gate B",
            "Ask any volunteer in a yellow vest",
            "Check the stadium app for maps and schedules",
        ],
        "urgent": False,
    },
    "crowd_analysis": {
        "summary": "Crowd data has been collected. Manual review recommended — AI analysis temporarily unavailable.",
        "severity": "moderate",
        "critical_zones": [],
        "recommendations": [
            "Review zone density data manually",
            "Contact zone supervisors for verbal status updates",
            "Monitor bottleneck zones via CCTV",
        ],
        "prediction": "Monitor current trends manually.",
        "alert_message": None,
    },
    "incident_classify": {
        "type": "unclassified",
        "severity": "medium",
        "confidence": "low",
        "recommendation": "AI classification unavailable. Please manually review this incident and assign type and severity.",
        "steps": [
            "Assess the situation in person or via CCTV",
            "Classify the incident type manually",
            "Dispatch appropriate resources",
            "Document in the incident log",
        ],
        "resources_required": ["Security officer"],
        "estimated_resolution_minutes": 20,
    },
    "volunteer_guidance": {
        "guidance": "Complete your assigned task by following your training protocols. Your zone supervisor is available if you need guidance.",
        "steps": [
            "Review your task description carefully",
            "Report to your zone supervisor if unclear",
            "Follow standard operating procedures",
            "Escalate any safety concerns immediately",
        ],
        "fan_phrases": [
            "How can I help you today?",
            "Please follow me, I'll show you the way.",
        ],
        "safety_notes": "Always prioritise safety. If in doubt, escalate immediately.",
        "escalate_if": "Any situation involving physical danger, medical emergency, or security threat.",
    },
    "event_briefing": {
        "title": "Operational Briefing — AI Service Temporarily Unavailable",
        "summary": "The AI briefing system is temporarily unavailable. Please review the live data dashboards for current crowd, incident, and volunteer status.",
        "key_points": [
            "Review crowd density data on the analytics dashboard",
            "Check active incident log for open cases",
            "Verify volunteer deployment via the volunteer console",
        ],
        "priorities": [
            "Review active incidents manually",
            "Check crowd density in all zones",
            "Confirm volunteer coverage",
        ],
        "action_items": [
            "Conduct manual status check with zone supervisors",
            "Review all open incidents and assign owners",
        ],
        "positive_indicators": ["Event is in progress"],
        "overall_status": "yellow",
    },
}


@dataclasses.dataclass
class AIResult:
    """Structured result returned by ai_service.ask()."""
    data: Dict[str, Any]
    intent: str
    from_cache: bool = False
    fallback_used: bool = False


def ask(persona: str, intent: str, context: Dict[str, Any]) -> AIResult:
    """
    Main entry point for all AI operations.

    Args:
        persona: "fan" | "organizer" | "volunteer" | "security"
        intent: AI pipeline intent (maps to a prompt template)
        context: Variables to inject into the prompt template

    Returns:
        AIResult with data, cache status, and fallback indicator.
    """
    # 1. Mock AI mode — skip Gemini, return realistic mock data
    if Config.MOCK_AI:
        logger.info("MOCK_AI=true — returning mock response for intent=%s", intent)
        return AIResult(
            data=_mock_response(intent, context),
            intent=intent,
            from_cache=False,
            fallback_used=False,
        )

    # 2. Build prompt
    try:
        prompt = prompt_manager.build(intent, context)
    except (KeyError, FileNotFoundError) as exc:
        logger.error("Prompt build failed for intent=%s: %s", intent, exc)
        return AIResult(data=FALLBACKS[intent], intent=intent, fallback_used=True)

    # 3. Cache lookup
    cached = cache.get(prompt, Config.AI_CACHE_TTL)
    if cached is not None:
        return AIResult(data=cached, intent=intent, from_cache=True)

    # 4. Call Gemini
    try:
        raw = _get_gemini().generate(prompt)
    except GeminiAPIError as exc:
        logger.warning("Gemini API error for intent=%s: %s", intent, str(exc)[:200])
        return AIResult(data=FALLBACKS[intent], intent=intent, fallback_used=True)

    # 5. Parse & validate
    try:
        parsed = parse(intent, raw)
    except AIOutputInvalidError as exc:
        logger.warning("AI output invalid for intent=%s: %s", intent, exc)
        return AIResult(data=FALLBACKS[intent], intent=intent, fallback_used=True)

    # 6. Cache and return
    cache.set(prompt, parsed, Config.AI_CACHE_TTL)
    return AIResult(data=parsed, intent=intent)


# ── Mock Responses (MOCK_AI=true) ─────────────────────────────────────────────

def _mock_response(intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Return realistic-looking mock AI responses for demo/offline mode."""
    mock_map = {
        "fan_chat": {
            "reply": "Great question! 🏟️ The nearest food court is Food Court East on Level 1, North Concourse — just 3 minutes from your seat. They serve American, Mexican, Brazilian and Indian cuisine. Current wait time is about 8 minutes. Enjoy the match!",
            "suggestions": [
                "Check Food Court West for shorter queues right now",
                "Pre-order food via the StadiumMind app to skip the line",
                "Gates open 4 hours before kickoff — arrive early to beat the rush",
            ],
            "urgent": False,
        },
        "crowd_analysis": {
            "summary": "MetLife Stadium is currently operating at 90% capacity with critical congestion in Food Court East and Exit Corridor North. Immediate attention is required to redistribute crowd flow before the halftime rush begins in approximately 12 minutes.",
            "severity": "high",
            "critical_zones": ["Food Court East", "Exit Corridor North"],
            "recommendations": [
                "Immediately deploy 3 additional crowd control volunteers to Food Court East",
                "Activate digital signage to redirect fans to Food Court West (8-min queue vs 20+)",
                "Open Exit Corridor South to absorb overflow from North Corridor",
                "Begin pre-halftime PA announcement for orderly concourse access",
                "Alert organizer supervisor for crowd situation escalation review",
            ],
            "prediction": "Halftime in ~12 minutes will trigger a significant surge in concourse zones. Expect 15-25% increase in concourse density. Exit corridors will peak at match end.",
            "alert_message": "High crowd density detected in Food Court East. Please use Food Court West for shorter wait times.",
        },
        "incident_classify": {
            "type": "crowd_surge",
            "severity": "high",
            "confidence": "high",
            "recommendation": "Immediate crowd control response required. Deploy personnel to establish access control at zone entry point. Redirect crowd flow to adjacent lower-density areas via PA and digital signage.",
            "steps": [
                "Step 1: Deploy 2 crowd control officers to zone entry immediately",
                "Step 2: Implement one-in-one-out access control at zone boundary",
                "Step 3: Activate digital signage displaying alternative routing",
                "Step 4: Issue PA announcement for crowd redirection",
                "Step 5: Monitor zone density every 3 minutes and escalate if no improvement",
            ],
            "resources_required": ["2x Crowd control officers", "Digital signage operator", "Zone supervisor"],
            "estimated_resolution_minutes": 15,
        },
        "volunteer_guidance": {
            "guidance": "Your task is high priority and involves direct crowd management. Maintain a calm, professional demeanor at all times. Your goal is to ensure safe fan flow through your zone while keeping wait times manageable.",
            "steps": [
                "Step 1: Position yourself visibly at the zone entry point in your yellow vest",
                "Step 2: Monitor the queue length every 5 minutes and report to your supervisor",
                "Step 3: Implement one-in-one-out when capacity reaches 80%",
                "Step 4: Redirect overflow fans to the alternative location with clear verbal direction",
                "Step 5: Report any fan frustration or potential conflict immediately via radio",
            ],
            "fan_phrases": [
                "'Food Court West is just 5 minutes away and has shorter queues right now!'",
                "'We appreciate your patience — we're keeping you safe. Thank you!'",
                "'Can I show you the way to an alternative area with no wait?'",
            ],
            "safety_notes": "If fans become aggressive or you feel unsafe, step back immediately and radio for security support. Never physically restrain anyone. Your safety comes first.",
            "escalate_if": "Fan count exceeds zone capacity by more than 10%, or any physical confrontation occurs, or a fan appears to be in medical distress.",
        },
        "event_briefing": {
            "title": "Operational Briefing — FRA vs GER — MetLife Stadium — June 17, 2026",
            "summary": "The France vs Germany Group B match is in progress at 90% capacity (74,250 fans). Operations are generally stable with two critical situations requiring immediate attention: Food Court East congestion and Exit Corridor North overcrowding. Medical units are responding to one high-severity cardiac event in Medical Bay A.",
            "key_points": [
                "Current attendance: 74,250 / 82,500 (90% capacity)",
                "2 critical zones active: Food Court East, Exit Corridor North",
                "10 total incidents logged — 6 active, 4 resolved",
                "10 volunteers deployed across 3 venues — 3 currently available",
                "Halftime expected in ~12 minutes — expect concourse surge",
                "Medical response ongoing in Medical Bay A (cardiac event)",
            ],
            "priorities": [
                "Resolve Exit Corridor North overcrowding before halftime surge",
                "Deploy additional resources to Food Court East congestion point",
                "Ensure ambulance access route is clear for Medical Bay A response",
            ],
            "action_items": [
                "Dispatch 2 additional crowd control volunteers to Exit Corridor North immediately",
                "Activate PA system with halftime crowd management announcement",
                "Confirm paramedic route from Gate A to Medical Bay A is unobstructed",
                "Brief all zone supervisors on halftime readiness via radio",
                "Prepare post-halftime crowd flow strategy for review at 21:30",
            ],
            "positive_indicators": [
                "Lost child incident resolved successfully (19:42)",
                "Azteca and BC Place venues operating within normal parameters",
                "Fan altercation at Azteca de-escalated without arrests",
            ],
            "overall_status": "orange",
        },
    }
    return mock_map.get(intent, FALLBACKS.get(intent, {"error": "Unknown intent"}))
