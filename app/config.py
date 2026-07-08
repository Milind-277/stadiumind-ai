"""
app/config.py — Centralised configuration management.
All settings are read from environment variables (via .env file).
No hardcoded secrets anywhere in the codebase.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration. All env vars with safe defaults for development."""

    # ── Flask Core ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    TESTING: bool = False

    # ── Google Gemini AI ───────────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    MOCK_AI: bool = os.environ.get("MOCK_AI", "false").lower() == "true"
    AI_MODEL: str = os.environ.get("AI_MODEL", "gemini-1.5-flash")
    AI_MAX_TOKENS: int = int(os.environ.get("AI_MAX_TOKENS", "1024"))
    AI_CACHE_TTL: int = int(os.environ.get("AI_CACHE_TTL", "300"))  # seconds

    # ── Data Storage ───────────────────────────────────────────────────────────
    DATA_DIR: str = os.environ.get("DATA_DIR", "data")

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "DEBUG")
    LOG_TO_FILE: bool = os.environ.get("LOG_TO_FILE", "false").lower() == "true"
    LOG_FILE: str = os.environ.get("LOG_FILE", "logs/stadiumind.log")

    # ── Session ────────────────────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── Security Headers ───────────────────────────────────────────────────────
    SECURITY_HEADERS: dict = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    @classmethod
    def validate(cls) -> None:
        """Raise at startup if critical config is missing in production."""
        if not cls.DEBUG and cls.SECRET_KEY == "dev-secret-key-change-in-prod":
            raise RuntimeError(
                "SECRET_KEY must be set to a strong random value in production."
            )
        if not cls.MOCK_AI and not cls.GEMINI_API_KEY:
            cls.MOCK_AI = True


class TestConfig(Config):
    """Isolated configuration for the test suite."""

    TESTING = True
    DEBUG = False
    MOCK_AI = True
    SECRET_KEY = "test-secret-key-not-for-production"
    DATA_DIR = "tests/fixtures"
    AI_CACHE_TTL = 0  # Disable cache in tests
