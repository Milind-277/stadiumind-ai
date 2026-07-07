"""app/ai/__init__.py"""
from .ai_service import ask, AIResult
from .gemini_client import GeminiClient, GeminiAPIError
from .response_parser import parse, AIOutputInvalidError
from . import cache, prompt_manager
from .decision_engine import (
    ContextBuilder,
    DecisionContext,
    DecisionEngine,
    PromptBuilder,
    build_decision_context,
    build_decision_prompt,
    recommend_actions,
)

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
