"""
tests/test_routes.py — Flask page route tests.

Covers:
  - Public routes (landing, health, switch-role)
  - Role selection (valid roles, invalid role → 400)
  - Authenticated page routes for all 4 personas
  - Role guard enforcement (unauthenticated → 302)
  - Cross-role access enforcement
"""

import pytest

# ===========================================================================
# Public Routes
# ===========================================================================


class TestPublicRoutes:
    """Tests for routes accessible without authentication."""

    def test_landing_page_renders(self, client):
        """Landing page must respond 200 and include 'StadiumMind'."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"StadiumMind" in resp.data

    def test_health_endpoint_returns_ok(self, client):
        """Health check must respond 200 with status=ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "StadiumMind AI"

    def test_health_endpoint_content_type_json(self, client):
        """Health endpoint must return JSON content type."""
        resp = client.get("/health")
        assert resp.content_type.startswith("application/json")

    def test_switch_role_redirects_to_landing(self, client):
        """GET /switch-role must redirect to landing (302)."""
        resp = client.get("/switch-role", follow_redirects=False)
        assert resp.status_code == 302
        assert "/" in resp.headers.get("Location", "")

    def test_switch_role_clears_session(self, fan_client):
        """Calling /switch-role removes role from session."""
        resp = fan_client.get("/switch-role", follow_redirects=True)
        assert resp.status_code == 200
        # After switch, landing page should be shown
        assert b"StadiumMind" in resp.data


# ===========================================================================
# Role Selection
# ===========================================================================


class TestRoleSelection:
    """Tests for POST /select-role."""

    @pytest.mark.parametrize("role", ["fan", "organizer", "volunteer", "security"])
    def test_valid_role_redirects(self, client, role):
        """Valid roles redirect to the persona home page."""
        resp = client.post(
            "/select-role",
            data={"role": role},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_invalid_role_returns_400(self, client):
        """An unrecognised role must return HTTP 400."""
        resp = client.post(
            "/select-role",
            data={"role": "hacker"},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_empty_role_returns_400(self, client):
        """An empty role value must return HTTP 400."""
        resp = client.post(
            "/select-role",
            data={"role": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_missing_role_field_returns_400(self, client):
        """POST without role field must return HTTP 400."""
        resp = client.post("/select-role", data={}, follow_redirects=False)
        assert resp.status_code == 400

    def test_landing_redirects_to_home_if_role_set(self, fan_client):
        """Landing page redirects to role-home when session role is already set."""
        resp = fan_client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/fan" in resp.headers.get("Location", "")


# ===========================================================================
# Fan Page Routes
# ===========================================================================


class TestFanRoutes:
    """Authenticated fan page route tests."""

    def test_fan_home(self, fan_client):
        """Fan home page renders successfully."""
        resp = fan_client.get("/fan/")
        assert resp.status_code == 200

    def test_fan_schedule(self, fan_client):
        """Fan schedule page renders successfully."""
        resp = fan_client.get("/fan/schedule")
        assert resp.status_code == 200

    def test_fan_wayfinding(self, fan_client):
        """Fan wayfinding page renders successfully."""
        resp = fan_client.get("/fan/wayfinding?venue_id=v001")
        assert resp.status_code == 200

    def test_fan_chat(self, fan_client):
        """Fan chat page renders successfully."""
        resp = fan_client.get("/fan/chat?venue_id=v001")
        assert resp.status_code == 200


# ===========================================================================
# Organizer Page Routes
# ===========================================================================


class TestOrganizerRoutes:
    """Authenticated organizer page route tests."""

    def test_organizer_home(self, organizer_client):
        """Organizer dashboard renders successfully."""
        resp = organizer_client.get("/organizer/")
        assert resp.status_code == 200

    def test_organizer_crowd(self, organizer_client):
        """Organizer crowd page renders successfully."""
        resp = organizer_client.get("/organizer/crowd")
        assert resp.status_code == 200

    def test_organizer_reports(self, organizer_client):
        """Organizer reports page renders successfully."""
        resp = organizer_client.get("/organizer/reports")
        assert resp.status_code == 200


# ===========================================================================
# Volunteer Page Routes
# ===========================================================================


class TestVolunteerRoutes:
    """Authenticated volunteer page route tests."""

    def test_volunteer_home(self, volunteer_client):
        """Volunteer console renders successfully."""
        resp = volunteer_client.get("/volunteer/")
        assert resp.status_code == 200

    def test_volunteer_tasks(self, volunteer_client):
        """Volunteer tasks page renders successfully."""
        resp = volunteer_client.get("/volunteer/tasks")
        assert resp.status_code == 200


# ===========================================================================
# Security Page Routes
# ===========================================================================


class TestSecurityRoutes:
    """Authenticated security page route tests."""

    def test_security_home(self, security_client):
        """Security command centre renders successfully."""
        resp = security_client.get("/security/")
        assert resp.status_code == 200

    def test_security_incidents(self, security_client):
        """Security incidents page renders successfully."""
        resp = security_client.get("/security/incidents")
        assert resp.status_code == 200


# ===========================================================================
# Role Guard — Unauthenticated Access
# ===========================================================================


class TestRoleGuardUnauthenticated:
    """Role guard redirects unauthenticated users to landing."""

    @pytest.mark.parametrize(
        "url",
        [
            "/fan/",
            "/organizer/",
            "/volunteer/",
            "/security/",
        ],
    )
    def test_page_redirects_without_role(self, client, url):
        """Page routes redirect to landing when no role is in session."""
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 302

    @pytest.mark.parametrize(
        "url",
        [
            "/fan/api/fan/matches",
            "/organizer/api/organizer/dashboard",
            "/volunteer/api/volunteer/tasks",
            "/security/api/security/incidents",
        ],
    )
    def test_api_returns_403_without_role(self, client, url):
        """API routes return 403 JSON when no role is in session."""
        resp = client.get(url)
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        assert any(err.get("code") == "ROLE_001" for err in data.get("errors", []))


# ===========================================================================
# Role Guard — Cross-Role Access Enforcement
# ===========================================================================


class TestRoleGuardCrossAccess:
    """Role guard blocks users from accessing other persona areas."""

    def test_fan_cannot_access_security(self, fan_client):
        """Fan role is blocked from security pages."""
        resp = fan_client.get("/security/", follow_redirects=False)
        assert resp.status_code == 302

    def test_fan_cannot_access_organizer(self, fan_client):
        """Fan role is blocked from organizer pages."""
        resp = fan_client.get("/organizer/", follow_redirects=False)
        assert resp.status_code == 302

    def test_fan_cannot_access_volunteer(self, fan_client):
        """Fan role is blocked from volunteer pages."""
        resp = fan_client.get("/volunteer/", follow_redirects=False)
        assert resp.status_code == 302

    def test_volunteer_cannot_access_organizer_api(self, volunteer_client):
        """Volunteer is blocked from organizer API routes."""
        resp = volunteer_client.get("/organizer/api/organizer/dashboard")
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False

    def test_security_cannot_access_fan_pages(self, security_client):
        """Security role is blocked from fan pages."""
        resp = security_client.get("/fan/", follow_redirects=False)
        assert resp.status_code == 302
