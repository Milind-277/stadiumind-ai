"""
tests/conftest.py — Shared pytest fixtures for StadiumMind AI test suite.

Fixtures:
    app       — Flask app configured with TestConfig (MOCK_AI=True)
    client    — Unauthenticated Flask test client
    fan_client / organizer_client / volunteer_client / security_client
              — Pre-authenticated test clients for each persona role
"""

import os

import pytest

# ── Ensure test environment before any app import ──────────────────────────────
os.environ.setdefault("MOCK_AI", "true")
os.environ.setdefault("FLASK_DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app import create_app  # noqa: E402 — must come after env setup
from app.config import TestConfig  # noqa: E402

# ---------------------------------------------------------------------------
# App + client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    """Create the Flask application using TestConfig (isolated from prod data)."""
    # Point TestConfig to the test fixtures directory
    TestConfig.DATA_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
    flask_app = create_app(config_class=TestConfig)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    yield flask_app


@pytest.fixture()
def client(app):
    """Unauthenticated test client — no session role set."""
    return app.test_client()


@pytest.fixture()
def fan_client(app):
    """Test client pre-authenticated as 'fan'."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["role"] = "fan"
    return c


@pytest.fixture()
def organizer_client(app):
    """Test client pre-authenticated as 'organizer'."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["role"] = "organizer"
    return c


@pytest.fixture()
def volunteer_client(app):
    """Test client pre-authenticated as 'volunteer'."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["role"] = "volunteer"
    return c


@pytest.fixture()
def security_client(app):
    """Test client pre-authenticated as 'security'."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["role"] = "security"
    return c


# ---------------------------------------------------------------------------
# Data / path helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixtures_dir():
    """Absolute path to the test fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def data_dir(fixtures_dir):
    """Alias for fixtures_dir — used by repository tests."""
    return fixtures_dir
