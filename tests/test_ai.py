"""
tests/test_ai.py — AI service, mock mode, fallback, cache, and parser tests.

Covers:
  - ask() in MOCK_AI mode for all intents
  - ask() returning fallback on prompt build failure
  - AIResult dataclass fields
  - FALLBACKS completeness (all intents have fallback)
  - Cache get/set/clear/stats
  - Response parser: valid schema, missing keys, non-dict input
  - Prompt manager: build, unknown intent, missing template
  - Mock response coverage for all intents
"""

from unittest.mock import patch

import pytest

from app.ai import cache
from app.ai.ai_service import FALLBACKS, AIResult, _mock_response, ask
from app.ai.prompt_manager import build as build_prompt
from app.ai.response_parser import REQUIRED_KEYS, AIOutputInvalidError, parse

# ===========================================================================
# AIResult Dataclass
# ===========================================================================


class TestAIResult:
    """Tests for the AIResult dataclass."""

    def test_airesult_defaults(self):
        """AIResult has sensible defaults for cache/fallback flags."""
        result = AIResult(data={"reply": "hello"}, intent="fan_chat")
        assert result.from_cache is False
        assert result.fallback_used is False

    def test_airesult_fields(self):
        """AIResult stores all fields correctly."""
        result = AIResult(
            data={"reply": "test"},
            intent="fan_chat",
            from_cache=True,
            fallback_used=False,
        )
        assert result.data == {"reply": "test"}
        assert result.intent == "fan_chat"
        assert result.from_cache is True


# ===========================================================================
# MOCK_AI Mode Tests
# ===========================================================================


class TestMockAIMode:
    """Tests for ask() when MOCK_AI=True (default in tests)."""

    def test_mock_mode_fan_chat(self):
        """MOCK_AI returns a fan_chat response without calling Gemini."""
        result = ask(
            "fan",
            "fan_chat",
            {"user_input": "Hello", "venue_context": "", "match_context": ""},
        )
        assert isinstance(result, AIResult)
        assert "reply" in result.data
        assert result.fallback_used is False

    def test_mock_mode_crowd_analysis(self):
        """MOCK_AI returns crowd_analysis mock response."""
        result = ask(
            "organizer",
            "crowd_analysis",
            {
                "venue_name": "MetLife",
                "timestamp": "2026-06-17",
                "total_attendance": "74000",
                "venue_capacity": "82500",
                "occupancy_pct": "90",
                "zone_data": "",
                "bottleneck_zones": "None",
            },
        )
        assert "summary" in result.data
        assert "severity" in result.data

    def test_mock_mode_incident_classify(self):
        """MOCK_AI returns incident_classify mock response."""
        result = ask(
            "security",
            "incident_classify",
            {
                "venue_name": "MetLife",
                "zone_name": "North Gate",
                "reported_at": "2026-06-17T20:00:00Z",
                "user_input": "Crowd surge",
            },
        )
        assert "type" in result.data
        assert "severity" in result.data
        assert "recommendation" in result.data

    def test_mock_mode_volunteer_guidance(self):
        """MOCK_AI returns volunteer_guidance mock response."""
        result = ask(
            "volunteer",
            "volunteer_guidance",
            {
                "volunteer_name": "Maria",
                "zone_name": "North Concourse",
                "task_title": "Crowd Control",
                "task_description": "Monitor zone",
                "priority": "high",
                "skills": "crowd_control",
                "languages": "English",
            },
        )
        assert "guidance" in result.data
        assert "steps" in result.data

    def test_mock_mode_event_briefing(self):
        """MOCK_AI returns event_briefing mock response."""
        result = ask(
            "organizer",
            "event_briefing",
            {
                "venue_name": "MetLife",
                "city": "New York",
                "country": "USA",
                "event_date": "2026-06-17",
                "match_summary": "FRA vs GER",
                "total_attendance": "74000",
                "venue_capacity": "82500",
                "occupancy_pct": "90",
                "crowd_summary": "High",
                "incident_count": "3",
                "incident_summary": "None",
                "volunteer_summary": "10 deployed",
            },
        )
        assert "title" in result.data
        assert "summary" in result.data

    def test_mock_mode_returns_correct_intent(self):
        """MOCK_AI result carries correct intent field."""
        result = ask(
            "fan",
            "fan_chat",
            {"user_input": "Hi", "venue_context": "", "match_context": ""},
        )
        assert result.intent == "fan_chat"

    def test_mock_response_unknown_intent(self):
        """_mock_response for unknown intent falls back to FALLBACKS."""
        result = _mock_response("unknown_intent", {})
        # Should return a fallback dict or error dict, but not raise
        assert isinstance(result, dict)


# ===========================================================================
# Fallback Coverage
# ===========================================================================


class TestFallbacks:
    """Tests that all intents have a defined fallback response."""

    EXPECTED_INTENTS = [
        "fan_chat",
        "crowd_analysis",
        "incident_classify",
        "volunteer_guidance",
        "event_briefing",
    ]

    @pytest.mark.parametrize("intent", EXPECTED_INTENTS)
    def test_fallback_exists(self, intent):
        """Each intent has a non-empty FALLBACKS entry."""
        assert intent in FALLBACKS, f"Missing FALLBACK for intent: {intent}"
        assert isinstance(
            FALLBACKS[intent], dict
        ), f"FALLBACK for '{intent}' must be a dict"
        assert FALLBACKS[intent], f"FALLBACK for '{intent}' is empty"

    def test_fan_chat_fallback_structure(self):
        """fan_chat fallback has reply and suggestions."""
        fb = FALLBACKS["fan_chat"]
        assert "reply" in fb
        assert "suggestions" in fb
        assert isinstance(fb["suggestions"], list)

    def test_incident_classify_fallback_structure(self):
        """incident_classify fallback has type, severity, recommendation."""
        fb = FALLBACKS["incident_classify"]
        assert "type" in fb
        assert "severity" in fb
        assert "recommendation" in fb

    def test_event_briefing_fallback_structure(self):
        """event_briefing fallback has title, summary, key_points, action_items."""
        fb = FALLBACKS["event_briefing"]
        assert "title" in fb
        assert "summary" in fb
        assert "key_points" in fb
        assert "action_items" in fb


# ===========================================================================
# Ask() Fallback Path Tests
# ===========================================================================


class TestAskFallbackPaths:
    """Tests that ask() gracefully returns fallback on failures."""

    def test_prompt_build_failure_returns_fallback(self):
        """ask() returns fallback when prompt build raises KeyError."""
        with patch("app.ai.ai_service.Config") as mock_cfg:
            mock_cfg.MOCK_AI = False
            mock_cfg.AI_CACHE_TTL = 0
            with patch(
                "app.ai.ai_service.prompt_manager.build",
                side_effect=KeyError("unknown"),
            ):
                result = ask("fan", "fan_chat", {})
        assert result.fallback_used is True

    def test_gemini_api_error_returns_fallback(self):
        """ask() returns fallback when Gemini raises GeminiAPIError."""
        from app.ai.gemini_client import GeminiAPIError

        with patch("app.ai.ai_service.Config") as mock_cfg:
            mock_cfg.MOCK_AI = False
            mock_cfg.AI_CACHE_TTL = 0
            mock_cfg.GEMINI_API_KEY = "fake-key"
            mock_cfg.AI_MODEL = "gemini-1.5-flash"
            mock_cfg.AI_MAX_TOKENS = 1024
            with patch("app.ai.ai_service.prompt_manager.build", return_value="prompt"):
                with patch("app.ai.ai_service.cache.get", return_value=None):
                    with patch("app.ai.ai_service._get_gemini") as mock_gemini:
                        mock_gemini.return_value.generate.side_effect = GeminiAPIError(
                            "API error"
                        )
                        result = ask("fan", "fan_chat", {})
        assert result.fallback_used is True
        assert "reply" in result.data

    def test_ai_output_invalid_returns_fallback(self):
        """ask() returns fallback when parse raises AIOutputInvalidError."""
        with patch("app.ai.ai_service.Config") as mock_cfg:
            mock_cfg.MOCK_AI = False
            mock_cfg.AI_CACHE_TTL = 0
            mock_cfg.GEMINI_API_KEY = "fake-key"
            mock_cfg.AI_MODEL = "gemini-1.5-flash"
            mock_cfg.AI_MAX_TOKENS = 1024
            with patch("app.ai.ai_service.prompt_manager.build", return_value="prompt"):
                with patch("app.ai.ai_service.cache.get", return_value=None):
                    with patch("app.ai.ai_service._get_gemini") as mock_gemini:
                        mock_gemini.return_value.generate.return_value = {
                            "invalid": True
                        }
                        with patch(
                            "app.ai.ai_service.parse",
                            side_effect=AIOutputInvalidError("bad"),
                        ):
                            result = ask("fan", "fan_chat", {})
        assert result.fallback_used is True

    def test_cache_hit_returns_cached_result(self):
        """ask() returns cached response when cache has valid entry."""
        cached_data = {"reply": "Cached response", "suggestions": [], "urgent": False}
        with patch("app.ai.ai_service.Config") as mock_cfg:
            mock_cfg.MOCK_AI = False
            mock_cfg.AI_CACHE_TTL = 300
            with patch("app.ai.ai_service.prompt_manager.build", return_value="prompt"):
                with patch("app.ai.ai_service.cache.get", return_value=cached_data):
                    result = ask("fan", "fan_chat", {})
        assert result.from_cache is True
        assert result.data == cached_data
        assert result.fallback_used is False


# ===========================================================================
# Cache Tests
# ===========================================================================


class TestCache:
    """Tests for the AI in-process cache module."""

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_miss_returns_none(self):
        """Cache returns None for unknown prompts."""
        result = cache.get("nonexistent-prompt", ttl=300)
        assert result is None

    def test_cache_set_and_get(self):
        """Stored entries can be retrieved within TTL."""
        data = {"reply": "hello"}
        cache.set("test-prompt", data, ttl=60)
        result = cache.get("test-prompt", ttl=60)
        assert result == data

    def test_cache_zero_ttl_never_stores(self):
        """TTL=0 disables caching (always miss)."""
        cache.set("test-prompt", {"reply": "hi"}, ttl=0)
        result = cache.get("test-prompt", ttl=0)
        assert result is None

    def test_cache_clear(self):
        """clear() removes all cache entries."""
        cache.set("prompt-a", {"x": 1}, ttl=300)
        cache.set("prompt-b", {"y": 2}, ttl=300)
        cache.clear()
        assert cache.get("prompt-a", ttl=300) is None
        assert cache.get("prompt-b", ttl=300) is None

    def test_cache_stats(self):
        """stats() returns correct active entry count."""
        cache.clear()
        cache.set("p1", {"a": 1}, ttl=300)
        cache.set("p2", {"b": 2}, ttl=300)
        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["active_entries"] == 2

    def test_different_prompts_cached_separately(self):
        """Different prompts have different cache keys."""
        cache.set("prompt-1", {"data": "one"}, ttl=300)
        cache.set("prompt-2", {"data": "two"}, ttl=300)
        assert cache.get("prompt-1", ttl=300) == {"data": "one"}
        assert cache.get("prompt-2", ttl=300) == {"data": "two"}


# ===========================================================================
# Response Parser Tests
# ===========================================================================


class TestResponseParser:
    """Tests for AI output validation and schema enforcement."""

    def test_valid_fan_chat_response(self):
        """Valid fan_chat response passes validation."""
        raw = {"reply": "Hello!", "suggestions": ["Go to Gate A"], "urgent": False}
        result = parse("fan_chat", raw)
        assert result["reply"] == "Hello!"

    def test_missing_required_key_raises(self):
        """Missing required key raises AIOutputInvalidError."""
        raw = {"reply": "Hello!"}  # missing 'suggestions'
        with pytest.raises(AIOutputInvalidError) as exc_info:
            parse("fan_chat", raw)
        assert "suggestions" in str(exc_info.value)

    def test_non_dict_input_raises(self):
        """Non-dict AI output raises AIOutputInvalidError."""
        with pytest.raises(AIOutputInvalidError):
            parse("fan_chat", "this is not a dict")

    def test_non_dict_list_input_raises(self):
        """List AI output raises AIOutputInvalidError."""
        with pytest.raises(AIOutputInvalidError):
            parse("fan_chat", ["item1", "item2"])

    def test_list_coercion(self):
        """String 'suggestions' is coerced to list."""
        raw = {"reply": "Hi", "suggestions": "just a string"}
        result = parse("fan_chat", raw)
        assert isinstance(result["suggestions"], list)

    def test_crowd_analysis_validation(self):
        """Valid crowd_analysis response passes."""
        raw = {
            "summary": "High occupancy",
            "severity": "high",
            "recommendations": ["Redirect fans"],
        }
        result = parse("crowd_analysis", raw)
        assert result["severity"] == "high"

    def test_incident_classify_validation(self):
        """Valid incident_classify response passes."""
        raw = {
            "type": "crowd_surge",
            "severity": "high",
            "recommendation": "Deploy crowd control",
        }
        result = parse("incident_classify", raw)
        assert result["type"] == "crowd_surge"

    def test_unknown_intent_no_required_keys(self):
        """Unknown intent has no required keys — any dict passes."""
        raw = {"anything": "here"}
        result = parse("unknown_intent_xyz", raw)
        assert result == raw

    def test_all_required_keys_present(self):
        """REQUIRED_KEYS covers all expected intents."""
        expected_intents = {
            "fan_chat",
            "crowd_analysis",
            "incident_classify",
            "volunteer_guidance",
            "event_briefing",
        }
        for intent in expected_intents:
            assert intent in REQUIRED_KEYS


# ===========================================================================
# Prompt Manager Tests
# ===========================================================================


class TestPromptManager:
    """Tests for the prompt template loading and building."""

    def test_build_unknown_intent_raises_key_error(self):
        """build() raises KeyError for unknown intent."""
        with pytest.raises(KeyError) as exc_info:
            build_prompt("totally_unknown_intent", {})
        assert "totally_unknown_intent" in str(exc_info.value)

    def test_build_fan_chat_returns_string(self):
        """build() returns a non-empty string for fan_chat."""
        prompt = build_prompt(
            "fan_chat",
            {
                "venue_context": "MetLife Stadium",
                "match_context": "FRA vs GER",
            },
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_injects_context_values(self):
        """build() injects context values into template placeholders."""
        prompt = build_prompt(
            "crowd_analysis",
            {
                "venue_name": "TEST_VENUE_NAME",
                "timestamp": "2026-06-17",
                "total_attendance": "50000",
                "venue_capacity": "82500",
                "occupancy_pct": "60",
                "zone_data": "Zone A: 500/1000",
                "bottleneck_zones": "None",
            },
        )
        # The venue name should appear in the generated prompt
        assert "TEST_VENUE_NAME" in prompt

    def test_build_sandboxes_user_input(self):
        """build() wraps user_input in XML tags for safety."""
        prompt = build_prompt(
            "fan_chat",
            {
                "venue_context": "Test",
                "match_context": "Test",
                "user_input": "Malicious <script>alert(1)</script>",
            },
        )
        assert "<user_input>" in prompt
        assert "Malicious" in prompt
