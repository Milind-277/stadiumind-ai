"""
tests/test_models.py — Domain model property and utility function tests.

Covers:
  - Match.is_live property (True/False)
  - Match.score_display property (with/without scores)
  - Incident.is_active property (open, investigating, resolved, contained)
  - All IncidentType enum values
  - All SeverityLevel enum values
  - All IncidentStatus enum values
  - All TaskStatus enum values
  - All TaskPriority enum values
  - format_match_time() formatting
  - time_until() past and future dates
  - success() response structure
  - error() response structure and status code
  - utcnow_iso() returns valid ISO string
"""

from datetime import datetime, timedelta, timezone

from app.models.incident import (Incident, IncidentStatus, IncidentType,
                                 SeverityLevel)
from app.models.match import Match, Team
from app.models.volunteer import TaskPriority, TaskStatus
from app.utils.datetime_utils import format_match_time, time_until, utcnow_iso
from app.utils.response import error, success

# ===========================================================================
# Helpers for creating model instances
# ===========================================================================


def _make_team(code: str = "TST") -> Team:
    return Team(
        id=f"t_{code.lower()}",
        name=f"Team {code}",
        code=code,
        flag_emoji="🏴",
        group="A",
    )


def _make_match(status: str = "scheduled", home_score=None, away_score=None) -> Match:
    return Match(
        id="m001",
        home_team=_make_team("HOM"),
        away_team=_make_team("AWY"),
        venue_id="v001",
        venue_name="Test Venue",
        kickoff_utc="2026-06-17T20:00:00+00:00",
        stage="Group Stage",
        group="A",
        status=status,
        home_score=home_score,
        away_score=away_score,
    )


def _make_incident(status: str = "open", severity: str = "medium") -> Incident:
    return Incident(
        id="i001",
        venue_id="v001",
        zone_id="z001",
        zone_name="North Concourse",
        type=IncidentType.CROWD_SURGE,
        severity=SeverityLevel(severity),
        status=IncidentStatus(status),
        description="Test incident",
        reported_by="test_volunteer",
        reported_at="2026-06-17T20:00:00Z",
    )


# ===========================================================================
# Match Model Tests
# ===========================================================================


class TestMatchModel:
    """Tests for the Match domain model."""

    def test_is_live_when_status_live(self):
        """Match.is_live returns True when status is 'live'."""
        match = _make_match(status="live")
        assert match.is_live is True

    def test_is_live_when_status_scheduled(self):
        """Match.is_live returns False when status is 'scheduled'."""
        match = _make_match(status="scheduled")
        assert match.is_live is False

    def test_is_live_when_status_completed(self):
        """Match.is_live returns False when status is 'completed'."""
        match = _make_match(status="completed")
        assert match.is_live is False

    def test_score_display_without_scores(self):
        """Match.score_display returns 'vs' when no scores set."""
        match = _make_match(home_score=None, away_score=None)
        assert match.score_display == "vs"

    def test_score_display_with_scores(self):
        """Match.score_display returns formatted score string."""
        match = _make_match(home_score=2, away_score=1)
        assert "2" in match.score_display
        assert "1" in match.score_display
        assert "–" in match.score_display

    def test_score_display_zero_zero(self):
        """Match.score_display handles 0-0 score correctly."""
        match = _make_match(home_score=0, away_score=0)
        assert match.score_display == "0 – 0"

    def test_team_attributes(self):
        """Team model has all required attributes."""
        team = _make_team("FRA")
        assert team.name == "Team FRA"
        assert team.code == "FRA"
        assert team.flag_emoji == "🏴"
        assert team.group == "A"


# ===========================================================================
# Incident Model Tests
# ===========================================================================


class TestIncidentModel:
    """Tests for the Incident domain model."""

    def test_is_active_when_open(self):
        """Incident.is_active returns True for status 'open'."""
        incident = _make_incident(status="open")
        assert incident.is_active is True

    def test_is_active_when_investigating(self):
        """Incident.is_active returns True for status 'investigating'."""
        incident = _make_incident(status="investigating")
        assert incident.is_active is True

    def test_is_active_when_contained(self):
        """Incident.is_active returns False for status 'contained'."""
        incident = _make_incident(status="contained")
        assert incident.is_active is False

    def test_is_active_when_resolved(self):
        """Incident.is_active returns False for status 'resolved'."""
        incident = _make_incident(status="resolved")
        assert incident.is_active is False


# ===========================================================================
# Enum Value Tests
# ===========================================================================


class TestIncidentEnums:
    """Tests for all incident-related enum values."""

    def test_incident_type_values(self):
        """All IncidentType enum values are valid strings."""
        expected = {
            "crowd_surge",
            "medical",
            "unauthorized_access",
            "fire_alarm",
            "suspicious_item",
            "fight",
            "lost_person",
            "structural",
            "unclassified",
        }
        actual = {t.value for t in IncidentType}
        assert expected == actual

    def test_severity_level_values(self):
        """All SeverityLevel enum values are correct."""
        expected = {"low", "medium", "high", "critical"}
        actual = {s.value for s in SeverityLevel}
        assert expected == actual

    def test_incident_status_values(self):
        """All IncidentStatus enum values are correct."""
        expected = {"open", "investigating", "contained", "resolved"}
        actual = {s.value for s in IncidentStatus}
        assert expected == actual

    def test_incident_type_str_enum(self):
        """IncidentType is a str enum (value == string)."""
        assert IncidentType.MEDICAL == "medical"
        assert IncidentType.CROWD_SURGE == "crowd_surge"


class TestVolunteerEnums:
    """Tests for all volunteer-related enum values."""

    def test_task_status_values(self):
        """All TaskStatus enum values are correct."""
        expected = {"pending", "in_progress", "completed", "escalated"}
        actual = {s.value for s in TaskStatus}
        assert expected == actual

    def test_task_priority_values(self):
        """All TaskPriority enum values are correct."""
        expected = {"low", "medium", "high", "urgent"}
        actual = {p.value for p in TaskPriority}
        assert expected == actual

    def test_task_status_str_enum(self):
        """TaskStatus is a str enum."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"


# ===========================================================================
# DateTime Utility Tests
# ===========================================================================


class TestDatetimeUtils:
    """Tests for date/time formatting utilities."""

    def test_utcnow_iso_returns_string(self):
        """utcnow_iso() returns a non-empty string."""
        result = utcnow_iso()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_utcnow_iso_is_parseable(self):
        """utcnow_iso() output can be parsed back to a datetime."""
        result = utcnow_iso()
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_format_match_time_valid_iso(self):
        """format_match_time() formats an ISO datetime correctly."""
        result = format_match_time("2026-06-17T20:00:00+00:00")
        assert "2026" in result
        assert "Jun" in result
        assert "20:00" in result

    def test_format_match_time_with_z_suffix(self):
        """format_match_time() handles 'Z' UTC suffix."""
        result = format_match_time("2026-06-17T20:00:00Z")
        assert "2026" in result

    def test_format_match_time_invalid_returns_original(self):
        """format_match_time() returns original string for invalid input."""
        result = format_match_time("not-a-date")
        assert result == "not-a-date"

    def test_format_match_time_empty_string(self):
        """format_match_time() handles empty string gracefully."""
        result = format_match_time("")
        assert isinstance(result, str)

    def test_time_until_future_hours(self):
        """time_until() returns 'in X hours' for future datetime."""
        future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        result = time_until(future)
        assert "in" in result
        assert "hour" in result

    def test_time_until_future_minutes(self):
        """time_until() returns 'in X minutes' for near-future datetime."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
        result = time_until(future)
        assert "in" in result
        assert "minute" in result

    def test_time_until_future_days(self):
        """time_until() returns 'in X days' for far-future datetime."""
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        result = time_until(future)
        assert "in" in result
        assert "day" in result

    def test_time_until_past_hours(self):
        """time_until() returns 'X hours ago' for past datetime."""
        past = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = time_until(past)
        assert "ago" in result
        assert "hour" in result

    def test_time_until_past_minutes(self):
        """time_until() returns 'X minutes ago' for recent past."""
        past = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        result = time_until(past)
        assert "ago" in result
        assert "minute" in result

    def test_time_until_past_days(self):
        """time_until() returns 'X days ago' for old past datetime."""
        past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        result = time_until(past)
        assert "ago" in result
        assert "day" in result

    def test_time_until_invalid_returns_empty(self):
        """time_until() returns empty string for invalid input."""
        result = time_until("not-a-date")
        assert result == ""


# ===========================================================================
# Response Utility Tests
# ===========================================================================


class TestResponseUtils:
    """Tests for the API response envelope builder."""

    def test_success_response_structure(self):
        """success() returns correct envelope structure."""
        resp = success(data={"key": "value"})
        assert resp["success"] is True
        assert resp["data"] == {"key": "value"}
        assert "meta" in resp
        assert resp["errors"] is None

    def test_success_meta_has_request_id(self):
        """success() meta includes request_id."""
        resp = success(data={})
        assert "request_id" in resp["meta"]
        assert len(resp["meta"]["request_id"]) > 0

    def test_success_meta_has_timestamp(self):
        """success() meta includes timestamp."""
        resp = success(data={})
        assert "timestamp" in resp["meta"]

    def test_success_ai_powered_flag(self):
        """success() passes ai_powered flag to meta."""
        resp = success(data={}, ai_powered=True)
        assert resp["meta"]["ai_powered"] is True

    def test_success_from_cache_flag(self):
        """success() passes from_cache flag to meta."""
        resp = success(data={}, from_cache=True)
        assert resp["meta"]["from_cache"] is True

    def test_success_fallback_used_flag(self):
        """success() passes fallback_used flag to meta."""
        resp = success(data={}, fallback_used=True)
        assert resp["meta"]["fallback_used"] is True

    def test_success_default_flags_are_false(self):
        """success() defaults ai_powered, from_cache, fallback_used to False."""
        resp = success(data={})
        assert resp["meta"]["ai_powered"] is False
        assert resp["meta"]["from_cache"] is False
        assert resp["meta"]["fallback_used"] is False

    def test_error_response_structure(self):
        """error() returns correct envelope structure."""
        resp, status = error("Something went wrong", "ERR_001")
        assert resp["success"] is False
        assert resp["data"] is None
        assert "meta" in resp
        assert isinstance(resp["errors"], list)
        assert len(resp["errors"]) == 1

    def test_error_status_code(self):
        """error() returns correct HTTP status code."""
        _, status = error("Not found", "NOT_FOUND", status_code=404)
        assert status == 404

    def test_error_default_status_code_is_400(self):
        """error() defaults to HTTP 400."""
        _, status = error("Bad request", "BAD")
        assert status == 400

    def test_error_message_content(self):
        """error() includes message in errors array."""
        resp, _ = error("Invalid input", "VAL_001")
        error_entry = resp["errors"][0]
        assert error_entry["message"] == "Invalid input"
        assert error_entry["code"] == "VAL_001"

    def test_error_with_field_includes_field(self):
        """error() with field param includes field in error object."""
        resp, _ = error("Field required", "VAL_001", field="name")
        assert resp["errors"][0]["field"] == "name"

    def test_error_500_status(self):
        """error() can return 500 status code."""
        resp, status = error("Server error", "INTERNAL_ERROR", status_code=500)
        assert status == 500
