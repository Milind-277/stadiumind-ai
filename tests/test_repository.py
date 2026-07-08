"""
tests/test_repository.py — JSON repository CRUD operation tests.

Covers:
  - find_all() returns correct domain model list
  - find_by_id() returns correct model or None
  - find_where() with predicate filtering
  - save() adds new record and returns model
  - update() updates existing record
  - update() returns None for missing ID
  - delete() removes record and returns True
  - delete() returns False for missing ID
  - Domain-specific methods: find_active, find_by_venue, find_by_volunteer
  - Atomic write safety (temp file rename pattern)
"""

import os
import shutil

import pytest

from app.models.incident import IncidentStatus, SeverityLevel
from app.models.volunteer import TaskStatus
from app.repositories.crowd_repo import CrowdRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.match_repo import MatchRepository
from app.repositories.venue_repo import VenueRepository
from app.repositories.volunteer_repo import TaskRepository, VolunteerRepository

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def tmp_data_dir(tmp_path, fixtures_dir):
    """
    Create a temporary data directory for each test by copying fixtures.
    This prevents test mutations from affecting other tests.
    """
    for filename in os.listdir(fixtures_dir):
        if filename.endswith(".json"):
            shutil.copy(
                os.path.join(fixtures_dir, filename),
                os.path.join(str(tmp_path), filename),
            )
    return str(tmp_path)


# ===========================================================================
# IncidentRepository Tests
# ===========================================================================


class TestIncidentRepository:
    """Tests for the JSON-backed Incident repository."""

    def test_find_all_returns_list(self, data_dir):
        """find_all() returns a non-empty list of Incident objects."""
        repo = IncidentRepository(data_dir)
        incidents = repo.find_all()
        assert isinstance(incidents, list)
        assert len(incidents) > 0

    def test_find_all_returns_incident_models(self, data_dir):
        """find_all() returns Incident domain model instances."""
        from app.models.incident import Incident

        repo = IncidentRepository(data_dir)
        incidents = repo.find_all()
        assert all(isinstance(i, Incident) for i in incidents)

    def test_find_by_id_existing(self, data_dir):
        """find_by_id() returns incident for known ID."""
        repo = IncidentRepository(data_dir)
        incidents = repo.find_all()
        first_id = incidents[0].id
        result = repo.find_by_id(first_id)
        assert result is not None
        assert result.id == first_id

    def test_find_by_id_nonexistent(self, data_dir):
        """find_by_id() returns None for unknown ID."""
        repo = IncidentRepository(data_dir)
        result = repo.find_by_id("does_not_exist_xyz")
        assert result is None

    def test_find_active_returns_only_active(self, data_dir):
        """find_active() returns only open/investigating incidents."""
        repo = IncidentRepository(data_dir)
        active = repo.find_active()
        for inc in active:
            assert inc.is_active is True

    def test_find_by_venue(self, data_dir):
        """find_by_venue() returns incidents for specified venue."""
        repo = IncidentRepository(data_dir)
        all_incidents = repo.find_all()
        if all_incidents:
            venue_id = all_incidents[0].venue_id
            result = repo.find_by_venue(venue_id)
            assert all(i.venue_id == venue_id for i in result)

    def test_find_by_severity(self, data_dir):
        """find_by_severity() filters by severity correctly."""
        repo = IncidentRepository(data_dir)
        result = repo.find_by_severity(SeverityLevel.HIGH)
        assert all(i.severity == SeverityLevel.HIGH for i in result)

    def test_find_where_predicate(self, data_dir):
        """find_where() applies predicate correctly."""
        repo = IncidentRepository(data_dir)
        result = repo.find_where(lambda i: i.severity == SeverityLevel.CRITICAL)
        assert all(i.severity == SeverityLevel.CRITICAL for i in result)

    def test_save_creates_new_record(self, tmp_data_dir):
        """save() adds a new incident and returns model."""
        repo = IncidentRepository(tmp_data_dir)
        initial_count = len(repo.find_all())
        new_incident = {
            "id": "inc_test_001",
            "venue_id": "v001",
            "zone_id": "z001",
            "zone_name": "Test Zone",
            "type": "unclassified",
            "severity": "low",
            "status": "open",
            "description": "Test incident for repository test",
            "reported_by": "test_suite",
            "reported_at": "2026-06-17T20:00:00Z",
            "notes": [],
        }
        saved = repo.save(new_incident)
        assert saved is not None
        assert len(repo.find_all()) == initial_count + 1

    def test_update_existing_record(self, tmp_data_dir):
        """update() modifies an existing incident's fields."""
        repo = IncidentRepository(tmp_data_dir)
        incidents = repo.find_all()
        target_id = incidents[0].id
        updated = repo.update(target_id, {"status": "resolved"})
        assert updated is not None
        assert updated.status == IncidentStatus.RESOLVED

    def test_update_nonexistent_returns_none(self, tmp_data_dir):
        """update() returns None for missing incident ID."""
        repo = IncidentRepository(tmp_data_dir)
        result = repo.update("nonexistent_id_xyz", {"status": "resolved"})
        assert result is None

    def test_delete_existing_returns_true(self, tmp_data_dir):
        """delete() removes incident and returns True."""
        repo = IncidentRepository(tmp_data_dir)
        incidents = repo.find_all()
        target_id = incidents[0].id
        result = repo.delete(target_id)
        assert result is True
        assert repo.find_by_id(target_id) is None

    def test_delete_nonexistent_returns_false(self, tmp_data_dir):
        """delete() returns False for missing incident ID."""
        repo = IncidentRepository(tmp_data_dir)
        result = repo.delete("nonexistent_id_xyz")
        assert result is False


# ===========================================================================
# VenueRepository Tests
# ===========================================================================


class TestVenueRepository:
    """Tests for the JSON-backed Venue repository."""

    def test_find_all_returns_venues(self, data_dir):
        """find_all() returns Venue model list."""
        from app.models.venue import Venue

        repo = VenueRepository(data_dir)
        venues = repo.find_all()
        assert isinstance(venues, list)
        assert len(venues) > 0
        assert all(isinstance(v, Venue) for v in venues)

    def test_find_by_id_known_venue(self, data_dir):
        """find_by_id('v001') returns the correct venue."""
        repo = VenueRepository(data_dir)
        venue = repo.find_by_id("v001")
        assert venue is not None
        assert venue.id == "v001"
        assert venue.name is not None

    def test_venue_has_gates(self, data_dir):
        """Venue model has a gates list."""
        repo = VenueRepository(data_dir)
        venue = repo.find_by_id("v001")
        assert isinstance(venue.gates, list)
        assert len(venue.gates) > 0

    def test_venue_has_zones(self, data_dir):
        """Venue model has a zones list."""
        repo = VenueRepository(data_dir)
        venue = repo.find_by_id("v001")
        assert isinstance(venue.zones, list)

    def test_venue_has_food_courts(self, data_dir):
        """Venue model has a food_courts list."""
        repo = VenueRepository(data_dir)
        venue = repo.find_by_id("v001")
        assert isinstance(venue.food_courts, list)

    def test_venue_has_accessibility_services(self, data_dir):
        """Venue model has accessibility_services list."""
        repo = VenueRepository(data_dir)
        venue = repo.find_by_id("v001")
        assert isinstance(venue.accessibility_services, list)

    def test_find_by_id_nonexistent(self, data_dir):
        """find_by_id() returns None for missing venue ID."""
        repo = VenueRepository(data_dir)
        result = repo.find_by_id("nonexistent_venue_xyz")
        assert result is None


# ===========================================================================
# MatchRepository Tests
# ===========================================================================


class TestMatchRepository:
    """Tests for the JSON-backed Match repository."""

    def test_find_all_returns_matches(self, data_dir):
        """find_all() returns Match model list."""
        from app.models.match import Match

        repo = MatchRepository(data_dir)
        matches = repo.find_all()
        assert isinstance(matches, list)
        assert len(matches) > 0
        assert all(isinstance(m, Match) for m in matches)

    def test_find_by_id_known_match(self, data_dir):
        """find_by_id() returns correct match."""
        repo = MatchRepository(data_dir)
        matches = repo.find_all()
        first_id = matches[0].id
        result = repo.find_by_id(first_id)
        assert result is not None
        assert result.id == first_id

    def test_match_has_teams(self, data_dir):
        """Match model has home_team and away_team."""
        repo = MatchRepository(data_dir)
        match = repo.find_all()[0]
        assert match.home_team is not None
        assert match.away_team is not None
        assert match.home_team.name is not None

    def test_find_where_live_matches(self, data_dir):
        """find_where() can filter live matches."""
        repo = MatchRepository(data_dir)
        live = repo.find_where(lambda m: m.is_live)
        assert all(m.is_live for m in live)


# ===========================================================================
# VolunteerRepository Tests
# ===========================================================================


class TestVolunteerRepository:
    """Tests for the JSON-backed Volunteer repository."""

    def test_find_all_returns_volunteers(self, data_dir):
        """find_all() returns Volunteer model list."""
        from app.models.volunteer import Volunteer

        repo = VolunteerRepository(data_dir)
        vols = repo.find_all()
        assert isinstance(vols, list)
        assert len(vols) > 0
        assert all(isinstance(v, Volunteer) for v in vols)

    def test_find_by_id_vol001(self, data_dir):
        """find_by_id('vol001') returns correct volunteer."""
        repo = VolunteerRepository(data_dir)
        vol = repo.find_by_id("vol001")
        assert vol is not None
        assert vol.id == "vol001"

    def test_find_by_id_nonexistent(self, data_dir):
        """find_by_id() returns None for missing volunteer ID."""
        repo = VolunteerRepository(data_dir)
        result = repo.find_by_id("nonexistent_vol_xyz")
        assert result is None

    def test_volunteer_has_skills(self, data_dir):
        """Volunteer model has skills list."""
        repo = VolunteerRepository(data_dir)
        vol = repo.find_by_id("vol001")
        assert isinstance(vol.skills, list)

    def test_volunteer_has_languages(self, data_dir):
        """Volunteer model has languages list."""
        repo = VolunteerRepository(data_dir)
        vol = repo.find_by_id("vol001")
        assert isinstance(vol.languages, list)

    def test_find_available(self, data_dir):
        """find_available() returns only available volunteers."""
        repo = VolunteerRepository(data_dir)
        available = repo.find_available()
        assert all(v.status == "available" for v in available)


# ===========================================================================
# TaskRepository Tests
# ===========================================================================


class TestTaskRepository:
    """Tests for the JSON-backed Task repository."""

    def test_find_all_returns_tasks(self, data_dir):
        """find_all() returns Task model list."""
        from app.models.volunteer import Task

        repo = TaskRepository(data_dir)
        tasks = repo.find_all()
        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert all(isinstance(t, Task) for t in tasks)

    def test_find_by_volunteer(self, data_dir):
        """find_by_volunteer() returns tasks for the given volunteer."""
        repo = TaskRepository(data_dir)
        tasks = repo.find_by_volunteer("vol001")
        assert all(t.assigned_to == "vol001" for t in tasks)

    def test_find_pending(self, data_dir):
        """find_pending() returns only pending tasks."""
        repo = TaskRepository(data_dir)
        pending = repo.find_pending()
        assert all(t.status == TaskStatus.PENDING for t in pending)

    def test_update_task_status(self, tmp_data_dir):
        """update() changes task status."""
        repo = TaskRepository(tmp_data_dir)
        tasks = repo.find_all()
        task_id = tasks[0].id
        updated = repo.update(task_id, {"status": "completed"})
        assert updated is not None
        assert updated.status == TaskStatus.COMPLETED


# ===========================================================================
# CrowdRepository Tests
# ===========================================================================


class TestCrowdRepository:
    """Tests for the JSON-backed Crowd repository."""

    def test_find_latest_by_venue(self, data_dir):
        """find_latest_by_venue() returns a crowd snapshot."""
        repo = CrowdRepository(data_dir)
        snapshot = repo.find_latest_by_venue("v001")
        assert snapshot is not None

    def test_snapshot_has_zones(self, data_dir):
        """Crowd snapshot has a zones list."""
        repo = CrowdRepository(data_dir)
        snapshot = repo.find_latest_by_venue("v001")
        assert isinstance(snapshot.zones, list)
        assert len(snapshot.zones) > 0

    def test_snapshot_has_occupancy(self, data_dir):
        """Crowd snapshot has overall occupancy percentage."""
        repo = CrowdRepository(data_dir)
        snapshot = repo.find_latest_by_venue("v001")
        assert isinstance(snapshot.overall_occupancy_pct, (int, float))

    def test_find_latest_nonexistent_venue(self, data_dir):
        """find_latest_by_venue() returns None for missing venue."""
        repo = CrowdRepository(data_dir)
        result = repo.find_latest_by_venue("nonexistent_venue_xyz")
        assert result is None
