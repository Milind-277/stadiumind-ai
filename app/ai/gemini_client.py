"""
app/ai/gemini_client.py — Google Gemini API wrapper.

Features:
- Structured JSON output enforcement
- Exponential backoff retry (2 retries)
- Timeout handling
- API key read from config (never hardcoded)
- Raises GeminiAPIError on exhausted retries
"""

import json
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Raised when the Gemini API call fails after all retries."""


class GeminiClient:
    """Thin wrapper around google-generativeai SDK with retry + structured output."""

    MAX_RETRIES = 2
    RETRY_DELAY = 1.5  # seconds, doubles each retry

    def __init__(
        self, api_key: str, model: str = "gemini-1.5-flash", max_tokens: int = 1024
    ):
        self.api_key = api_key
        self.model_name = model
        self.max_tokens = max_tokens
        self._model = None
        self._initialized = False

    def _init_model(self) -> None:
        """Lazy initialisation — only import SDK when first needed."""
        if self._initialized:
            return
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": self.max_tokens,
                    "temperature": 0.4,
                },
            )
            self._initialized = True
            logger.info("Gemini client initialised", extra={"model": self.model_name})
        except ImportError as exc:
            raise GeminiAPIError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            ) from exc

    def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Send prompt to Gemini and return parsed JSON dict.
        Retries up to MAX_RETRIES times with exponential backoff.
        Raises GeminiAPIError on failure.
        """
        self._init_model()
        delay = self.RETRY_DELAY

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug("Gemini call attempt %d", attempt + 1)
                response = self._model.generate_content(prompt)
                text = response.text.strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                parsed = json.loads(text)
                logger.debug("Gemini call success, attempt %d", attempt + 1)
                return parsed
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Gemini returned non-JSON output on attempt %d", attempt + 1
                )
                raise GeminiAPIError("Gemini returned non-JSON output.") from exc
            except Exception as exc:
                err_str = str(exc)
                logger.warning(
                    "Gemini API error on attempt %d: %s", attempt + 1, err_str[:200]
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise GeminiAPIError(
                        f"Gemini API failed after {self.MAX_RETRIES + 1} attempts."
                    ) from exc

        raise GeminiAPIError("Gemini API failed — exhausted retries.")
