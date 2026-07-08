"""app/ai/__init__.py"""

from . import cache, prompt_manager
from .ai_service import AIResult, ask
from .decision_engine import (ContextBuilder, DecisionContext, DecisionEngine,
                              PromptBuilder, build_decision_context,
                              build_decision_prompt, recommend_actions)
from .gemini_client import GeminiAPIError, GeminiClient
from .response_parser import AIOutputInvalidError, parse

__all__ = [
    "ask",
    "AIResult",
    "GeminiClient",
    "GeminiAPIError",
    "parse",
    "AIOutputInvalidError",
    "cache",
    "prompt_manager",
    "ContextBuilder",
    "DecisionContext",
    "DecisionEngine",
    "PromptBuilder",
    "build_decision_context",
    "build_decision_prompt",
    "recommend_actions",
]
