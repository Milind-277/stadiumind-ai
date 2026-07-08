"""
tests/test_api.py — REST API endpoint tests.

Covers:
  - Fan API: matches, chat, wayfinding, venue
  - Organizer API: dashboard, crowd, crowd analysis, reports, alerts, incidents
  - Security API: incidents (GET/POST/PATCH/classify), heatmap, protocols
  - Volunteer API: profile, tasks, task update, AI guidance, SOS
  - Input validation: empty payloads, missing fields, malformed JSON
  - Invalid IDs → 404 responses
  - JSON schema validation on all responses
"""

import json

# ===========================================================================
# Helper
# ===========================================================================


def _json(resp):
    """Return parsed JSON body from a response."""
    return resp.get_json()


def _ok(resp):
    """Assert 2xx and success=True in response body."""
    data = _json(resp)
    assert resp.status_code in (
        200,
        201,
    ), f"Expected 2xx, got {resp.status_code}: {data}"
    assert data.get("success") is True, f"Expected success=True, got: {data}"
    return data


def _err(resp, expected_status=400):
    """Assert expected error status and success=False."""
    data = _json(resp)
    assert (
        resp.status_code == expected_status
    ), f"Expected {expected_status}, got {resp.status_code}: {data}"
    assert data.get("success") is False, f"Expected success=False, got: {data}"
    return data


# ===========================================================================
# Fan API Tests
# ===========================================================================


class TestFanAPI:
    """Tests for Fan persona REST API endpoints."""

    def test_get_matches_returns_list(self, fan_client):
        """GET /fan/api/fan/matches returns match list."""
        resp = fan_client.get("/fan/api/fan/matches")
        data = _ok(resp)
        assert "matches" in data["data"]
        assert isinstance(data["data"]["matches"], list)

    def test_get_matches_structure(self, fan_client):
        """Each match has required fields."""
        resp = fan_client.get("/fan/api/fan/matches")
        data = _ok(resp)
        for match in data["data"]["matches"]:
            assert "id" in match
            assert "home_team" in match
            assert "away_team" in match
            assert "status" in match

    def test_get_match_detail_valid_id(self, fan_client):
        """GET /fan/api/fan/matches/m001 returns match detail."""
        resp = fan_client.get("/fan/api/fan/matches/m001")
        data = _ok(resp)
        assert "id" in data["data"]

    def test_get_match_detail_invalid_id(self, fan_client):
        """Invalid match ID returns 404."""
        resp = fan_client.get("/fan/api/fan/matches/nonexistent_id_xyz")
        _err(resp, 404)

    def test_fan_chat_valid_message(self, fan_client):
        """POST /fan/api/fan/chat with valid message returns reply."""
        resp = fan_client.post(
            "/fan/api/fan/chat",
            data=json.dumps(
                {"message": "Where is the nearest food court?", "venue_id": "v001"}
            ),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "reply" in data["data"]
        assert "suggestions" in data["data"]

    def test_fan_chat_missing_message_returns_400(self, fan_client):
        """POST /fan/api/fan/chat without message field returns 400."""
        resp = fan_client.post(
            "/fan/api/fan/chat",
            data=json.dumps({"venue_id": "v001"}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_fan_chat_empty_body_returns_400(self, fan_client):
        """POST /fan/api/fan/chat with empty body returns 400."""
        resp = fan_client.post(
            "/fan/api/fan/chat",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_fan_chat_malformed_json(self, fan_client):
        """POST /fan/api/fan/chat with malformed JSON still handles gracefully."""
        resp = fan_client.post(
            "/fan/api/fan/chat",
            data="not-valid-json",
            content_type="application/json",
        )
        # Should still return 400 — missing 'message' field
        assert resp.status_code == 400

    def test_fan_wayfinding_valid(self, fan_client):
        """GET /fan/api/fan/wayfinding with valid params returns directions."""
        resp = fan_client.get("/fan/api/fan/wayfinding?venue_id=v001&to=Gate+A")
        data = _ok(resp)
        assert "ai_guidance" in data["data"]
        assert "gates" in data["data"]

    def test_fan_wayfinding_missing_to_param(self, fan_client):
        """GET wayfinding without 'to' param returns 400."""
        resp = fan_client.get("/fan/api/fan/wayfinding?venue_id=v001")
        _err(resp, 400)

    def test_fan_venue_valid_id(self, fan_client):
        """GET /fan/api/fan/venue/v001 returns venue data."""
        resp = fan_client.get("/fan/api/fan/venue/v001")
        data = _ok(resp)
        assert "name" in data["data"]
        assert "capacity" in data["data"]

    def test_fan_venue_invalid_id(self, fan_client):
        """GET /fan/api/fan/venue/<invalid> returns 404."""
        resp = fan_client.get("/fan/api/fan/venue/nonexistent_xyz")
        _err(resp, 404)

    def test_response_meta_structure(self, fan_client):
        """All success responses include meta with request_id and timestamp."""
        resp = fan_client.get("/fan/api/fan/matches")
        data = _json(resp)
        assert "meta" in data
        assert "request_id" in data["meta"]
        assert "timestamp" in data["meta"]

    def test_fan_api_requires_role(self, client):
        """Fan API endpoints return 403 without role in session."""
        resp = client.get("/fan/api/fan/matches")
        _err(resp, 403)


# ===========================================================================
# Organizer API Tests
# ===========================================================================


class TestOrganizerAPI:
    """Tests for Organizer persona REST API endpoints."""

    def test_dashboard_returns_summary(self, organizer_client):
        """GET /organizer/api/organizer/dashboard returns summary data."""
        resp = organizer_client.get("/organizer/api/organizer/dashboard")
        data = _ok(resp)
        assert "total_active_incidents" in data["data"]
        assert "total_volunteers" in data["data"]
        assert "venues" in data["data"]

    def test_crowd_live_all_venues(self, organizer_client):
        """GET crowd/live without venue_id returns all venues."""
        resp = organizer_client.get("/organizer/api/organizer/crowd/live")
        data = _ok(resp)
        assert "venues" in data["data"]
        assert isinstance(data["data"]["venues"], list)

    def test_crowd_live_specific_venue(self, organizer_client):
        """GET crowd/live?venue_id=v001 returns data for that venue."""
        resp = organizer_client.get("/organizer/api/organizer/crowd/live?venue_id=v001")
        data = _ok(resp)
        assert "venues" in data["data"]

    def test_crowd_analysis_valid_venue(self, organizer_client):
        """GET crowd/analysis?venue_id=v001 returns AI analysis."""
        resp = organizer_client.get(
            "/organizer/api/organizer/crowd/analysis?venue_id=v001"
        )
        data = _ok(resp)
        assert "analysis" in data["data"]
        assert "venue_name" in data["data"]

    def test_crowd_analysis_invalid_venue(self, organizer_client):
        """GET crowd/analysis with invalid venue_id returns 404."""
        resp = organizer_client.get(
            "/organizer/api/organizer/crowd/analysis?venue_id=invalid_xyz"
        )
        _err(resp, 404)

    def test_generate_report_valid(self, organizer_client):
        """POST /organizer/api/organizer/reports/generate returns briefing."""
        resp = organizer_client.post(
            "/organizer/api/organizer/reports/generate",
            data=json.dumps({"venue_id": "v001"}),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "briefing" in data["data"]

    def test_generate_report_invalid_venue(self, organizer_client):
        """POST reports/generate with invalid venue_id returns 404."""
        resp = organizer_client.post(
            "/organizer/api/organizer/reports/generate",
            data=json.dumps({"venue_id": "nonexistent"}),
            content_type="application/json",
        )
        _err(resp, 404)

    def test_broadcast_alert_valid(self, organizer_client):
        """POST alerts/broadcast with all fields returns alert data."""
        resp = organizer_client.post(
            "/organizer/api/organizer/alerts/broadcast",
            data=json.dumps(
                {
                    "title": "Test Alert",
                    "message": "This is a test alert message",
                    "priority": "medium",
                    "venue_id": "v001",
                }
            ),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "alert" in data["data"]
        assert data["data"]["broadcast"] is True

    def test_broadcast_alert_missing_title(self, organizer_client):
        """POST alerts/broadcast missing title returns 400."""
        resp = organizer_client.post(
            "/organizer/api/organizer/alerts/broadcast",
            data=json.dumps(
                {
                    "message": "No title here",
                    "priority": "medium",
                    "venue_id": "v001",
                }
            ),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_broadcast_alert_empty_payload(self, organizer_client):
        """POST alerts/broadcast with empty JSON returns 400."""
        resp = organizer_client.post(
            "/organizer/api/organizer/alerts/broadcast",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_get_incidents(self, organizer_client):
        """GET /organizer/api/organizer/incidents returns incident list."""
        resp = organizer_client.get("/organizer/api/organizer/incidents")
        data = _ok(resp)
        assert "incidents" in data["data"]
        assert "total" in data["data"]

    def test_organizer_api_requires_role(self, client):
        """Organizer API returns 403 without role."""
        resp = client.get("/organizer/api/organizer/dashboard")
        _err(resp, 403)


# ===========================================================================
# Security API Tests
# ===========================================================================


class TestSecurityAPI:
    """Tests for Security persona REST API endpoints."""

    def test_get_incidents_all(self, security_client):
        """GET /security/api/security/incidents returns all incidents."""
        resp = security_client.get("/security/api/security/incidents")
        data = _ok(resp)
        assert "incidents" in data["data"]
        assert "total" in data["data"]
        assert "active" in data["data"]

    def test_get_incidents_by_venue(self, security_client):
        """GET incidents?venue_id=v001 filters by venue."""
        resp = security_client.get("/security/api/security/incidents?venue_id=v001")
        data = _ok(resp)
        assert "incidents" in data["data"]

    def test_log_incident_valid(self, security_client):
        """POST /security/api/security/incidents logs a new incident."""
        resp = security_client.post(
            "/security/api/security/incidents",
            data=json.dumps(
                {
                    "venue_id": "v001",
                    "zone_id": "z001",
                    "zone_name": "North Concourse",
                    "description": "Suspicious behaviour observed near Gate A.",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = _json(resp)
        assert data["success"] is True
        assert "id" in data["data"]

    def test_log_incident_missing_venue_id(self, security_client):
        """POST incidents without venue_id returns 400."""
        resp = security_client.post(
            "/security/api/security/incidents",
            data=json.dumps(
                {
                    "zone_id": "z001",
                    "zone_name": "North Concourse",
                    "description": "Test incident",
                }
            ),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_log_incident_empty_payload(self, security_client):
        """POST incidents with empty JSON returns 400."""
        resp = security_client.post(
            "/security/api/security/incidents",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_update_incident_valid(self, security_client):
        """PATCH incident updates status field."""
        resp = security_client.patch(
            "/security/api/security/incidents/inc001",
            data=json.dumps({"status": "investigating"}),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "id" in data["data"]

    def test_update_incident_no_valid_fields(self, security_client):
        """PATCH incident with no valid update fields returns 400."""
        resp = security_client.patch(
            "/security/api/security/incidents/inc001",
            data=json.dumps({"invalid_field": "value"}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_update_incident_invalid_id(self, security_client):
        """PATCH nonexistent incident returns 404."""
        resp = security_client.patch(
            "/security/api/security/incidents/nonexistent_id_xyz",
            data=json.dumps({"status": "resolved"}),
            content_type="application/json",
        )
        _err(resp, 404)

    def test_classify_incident_valid(self, security_client):
        """POST classify on valid incident returns classification."""
        resp = security_client.post("/security/api/security/incidents/inc002/classify")
        data = _ok(resp)
        assert "classification" in data["data"]
        assert "incident_id" in data["data"]

    def test_classify_incident_invalid_id(self, security_client):
        """POST classify on nonexistent incident returns 404."""
        resp = security_client.post(
            "/security/api/security/incidents/nonexistent_xyz/classify"
        )
        _err(resp, 404)

    def test_heatmap_valid_venue(self, security_client):
        """GET heatmap?venue_id=v001 returns zone density data."""
        resp = security_client.get("/security/api/security/zones/heatmap?venue_id=v001")
        data = _ok(resp)
        assert "zones" in data["data"]
        assert "venue_name" in data["data"]

    def test_heatmap_invalid_venue(self, security_client):
        """GET heatmap with invalid venue_id returns 404."""
        resp = security_client.get(
            "/security/api/security/zones/heatmap?venue_id=invalid_xyz"
        )
        _err(resp, 404)

    def test_protocol_known_type(self, security_client):
        """GET protocol for 'medical' returns protocol steps."""
        resp = security_client.get("/security/api/security/protocols/medical")
        data = _ok(resp)
        assert "protocol" in data["data"]
        assert "steps" in data["data"]["protocol"]

    def test_protocol_unknown_type_returns_general(self, security_client):
        """GET protocol for unknown incident type returns general protocol."""
        resp = security_client.get("/security/api/security/protocols/unknown_type")
        data = _ok(resp)
        assert "protocol" in data["data"]

    def test_security_api_requires_role(self, client):
        """Security API returns 403 without role."""
        resp = client.get("/security/api/security/incidents")
        _err(resp, 403)


# ===========================================================================
# Volunteer API Tests
# ===========================================================================


class TestVolunteerAPI:
    """Tests for Volunteer persona REST API endpoints."""

    def test_get_profile(self, volunteer_client):
        """GET /volunteer/api/volunteer/profile returns volunteer data."""
        resp = volunteer_client.get("/volunteer/api/volunteer/profile")
        data = _ok(resp)
        assert "id" in data["data"]
        assert "name" in data["data"]
        assert "skills" in data["data"]

    def test_get_tasks(self, volunteer_client):
        """GET /volunteer/api/volunteer/tasks returns task list."""
        resp = volunteer_client.get("/volunteer/api/volunteer/tasks")
        data = _ok(resp)
        assert "tasks" in data["data"]
        assert "total" in data["data"]

    def test_get_tasks_structure(self, volunteer_client):
        """Each task has required fields."""
        resp = volunteer_client.get("/volunteer/api/volunteer/tasks")
        data = _ok(resp)
        for task in data["data"]["tasks"]:
            assert "id" in task
            assert "title" in task
            assert "priority" in task
            assert "status" in task

    def test_update_task_valid_status(self, volunteer_client):
        """PATCH task with valid status returns updated task."""
        resp = volunteer_client.patch(
            "/volunteer/api/volunteer/tasks/t001",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "id" in data["data"]

    def test_update_task_missing_status(self, volunteer_client):
        """PATCH task without status field returns 400."""
        resp = volunteer_client.patch(
            "/volunteer/api/volunteer/tasks/t001",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_update_task_invalid_status(self, volunteer_client):
        """PATCH task with invalid status value returns 404."""
        resp = volunteer_client.patch(
            "/volunteer/api/volunteer/tasks/t001",
            data=json.dumps({"status": "flying_to_moon"}),
            content_type="application/json",
        )
        _err(resp, 404)

    def test_update_task_invalid_id(self, volunteer_client):
        """PATCH nonexistent task returns 404."""
        resp = volunteer_client.patch(
            "/volunteer/api/volunteer/tasks/nonexistent_task_xyz",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        _err(resp, 404)

    def test_ai_guidance_valid_task(self, volunteer_client):
        """POST ai-guidance with valid task_id returns guidance."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/ai-guidance",
            data=json.dumps({"task_id": "t001"}),
            content_type="application/json",
        )
        data = _ok(resp)
        assert "guidance" in data["data"]
        assert "task_id" in data["data"]

    def test_ai_guidance_missing_task_id(self, volunteer_client):
        """POST ai-guidance without task_id returns 400."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/ai-guidance",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_ai_guidance_invalid_task_id(self, volunteer_client):
        """POST ai-guidance with invalid task_id returns 404."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/ai-guidance",
            data=json.dumps({"task_id": "nonexistent_xyz"}),
            content_type="application/json",
        )
        _err(resp, 404)

    def test_sos_valid_payload(self, volunteer_client):
        """POST SOS with all required fields returns success."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/sos",
            data=json.dumps(
                {
                    "description": "Fan collapsed near food court",
                    "zone_id": "z001",
                    "zone_name": "North Concourse",
                    "venue_id": "v001",
                }
            ),
            content_type="application/json",
        )
        data = _ok(resp)
        assert data["data"]["sos_submitted"] is True
        assert "incident_id" in data["data"]

    def test_sos_missing_description(self, volunteer_client):
        """POST SOS without description returns 400."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/sos",
            data=json.dumps(
                {
                    "zone_id": "z001",
                    "zone_name": "North Concourse",
                    "venue_id": "v001",
                }
            ),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_sos_empty_payload(self, volunteer_client):
        """POST SOS with empty JSON returns 400."""
        resp = volunteer_client.post(
            "/volunteer/api/volunteer/sos",
            data=json.dumps({}),
            content_type="application/json",
        )
        _err(resp, 400)

    def test_volunteer_api_requires_role(self, client):
        """Volunteer API returns 403 without role."""
        resp = client.get("/volunteer/api/volunteer/tasks")
        _err(resp, 403)
