"""
tests/test_security.py — Security header, role guard, and input validation tests.

Covers:
  - HTTP security headers on all responses (CSP, X-Frame-Options, etc.)
  - Role guard — no session: page → 302, API → 403 JSON
  - Role guard — wrong role: page → 302, API → 403 JSON
  - Role selection XSS / injection attempts
  - sanitize_string() XSS prevention
  - is_valid_id() allowlist validation
  - Error response structure (success=False, errors array)
"""

import pytest

from app.utils.validators import is_valid_id, require_fields, sanitize_string

# ===========================================================================
# Security Headers
# ===========================================================================


class TestSecurityHeaders:
    """Tests that all responses include required security headers."""

    EXPECTED_HEADERS = [
        ("X-Frame-Options", "DENY"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-XSS-Protection", "1; mode=block"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ]

    def test_landing_page_has_security_headers(self, client):
        """Landing page response includes all security headers."""
        resp = client.get("/")
        for header, expected_value in self.EXPECTED_HEADERS:
            assert header in resp.headers, f"Missing header: {header}"
            assert expected_value in resp.headers[header], (
                f"Header '{header}' value '{resp.headers[header]}' "
                f"does not contain '{expected_value}'"
            )

    def test_health_endpoint_has_security_headers(self, client):
        """Health endpoint response includes all security headers."""
        resp = client.get("/health")
        for header, expected_value in self.EXPECTED_HEADERS:
            assert header in resp.headers

    def test_api_response_has_security_headers(self, fan_client):
        """API responses include all security headers."""
        resp = fan_client.get("/fan/api/fan/matches")
        for header, _ in self.EXPECTED_HEADERS:
            assert header in resp.headers

    def test_csp_header_present(self, client):
        """Content-Security-Policy header is set on all responses."""
        resp = client.get("/")
        assert "Content-Security-Policy" in resp.headers

    def test_csp_header_includes_default_src(self, client):
        """CSP header includes 'default-src' directive."""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp

    def test_csp_header_self_policy(self, client):
        """CSP header includes 'self' as a source."""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "'self'" in csp

    def test_x_frame_options_denies_framing(self, client):
        """X-Frame-Options must be DENY to prevent clickjacking."""
        resp = client.get("/")
        assert resp.headers.get("X-Frame-Options") == "DENY"


# ===========================================================================
# Role Guard — No Session
# ===========================================================================


class TestRoleGuardNoSession:
    """Role guard must block access when no session role is set."""

    @pytest.mark.parametrize(
        "url",
        [
            "/fan/",
            "/organizer/",
            "/volunteer/",
            "/security/",
            "/fan/schedule",
            "/organizer/crowd",
            "/volunteer/tasks",
            "/security/incidents",
        ],
    )
    def test_page_redirect_without_session(self, client, url):
        """Page routes redirect (302) to landing when no session role."""
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
    def test_api_returns_403_without_session(self, client, url):
        """API routes return HTTP 403 when no session role."""
        resp = client.get(url)
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        # Should have ROLE_001 error code
        codes = [e.get("code") for e in data.get("errors", [])]
        assert "ROLE_001" in codes


# ===========================================================================
# Role Guard — Wrong Role
# ===========================================================================


class TestRoleGuardWrongRole:
    """Role guard must block cross-persona access."""

    def test_fan_blocked_from_organizer_api(self, fan_client):
        """Fan cannot access organizer API (returns 403)."""
        resp = fan_client.get("/organizer/api/organizer/dashboard")
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        codes = [e.get("code") for e in data.get("errors", [])]
        assert "ROLE_002" in codes

    def test_fan_blocked_from_security_api(self, fan_client):
        """Fan cannot access security API (returns 403)."""
        resp = fan_client.get("/security/api/security/incidents")
        assert resp.status_code == 403

    def test_organizer_blocked_from_fan_api(self, organizer_client):
        """Organizer cannot access fan API (returns 403)."""
        resp = organizer_client.get("/fan/api/fan/matches")
        assert resp.status_code == 403

    def test_volunteer_blocked_from_security_api(self, volunteer_client):
        """Volunteer cannot access security API (returns 403)."""
        resp = volunteer_client.get("/security/api/security/incidents")
        assert resp.status_code == 403

    def test_security_blocked_from_volunteer_api(self, security_client):
        """Security cannot access volunteer API (returns 403)."""
        resp = security_client.get("/volunteer/api/volunteer/tasks")
        assert resp.status_code == 403

    def test_fan_blocked_from_organizer_page(self, fan_client):
        """Fan is redirected (302) from organizer page."""
        resp = fan_client.get("/organizer/", follow_redirects=False)
        assert resp.status_code == 302

    def test_fan_blocked_from_volunteer_page(self, fan_client):
        """Fan is redirected (302) from volunteer page."""
        resp = fan_client.get("/volunteer/", follow_redirects=False)
        assert resp.status_code == 302


# ===========================================================================
# Input Validation — sanitize_string
# ===========================================================================


class TestSanitizeString:
    """Tests for XSS prevention and string sanitization."""

    def test_html_tags_are_escaped(self):
        """HTML tags are escaped to prevent XSS."""
        result = sanitize_string("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_angle_brackets_escaped(self):
        """Angle brackets are HTML-escaped."""
        result = sanitize_string("<b>bold</b>")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_truncation_to_max_length(self):
        """String is truncated to max_length characters."""
        long_str = "a" * 1000
        result = sanitize_string(long_str, max_length=100)
        assert len(result) == 100

    def test_whitespace_stripped(self):
        """Leading and trailing whitespace is stripped."""
        result = sanitize_string("  hello world  ")
        assert result == "hello world"

    def test_none_value_returns_empty_string(self):
        """None input returns empty string."""
        result = sanitize_string(None)
        assert result == ""

    def test_non_string_converted(self):
        """Non-string values are converted to string."""
        result = sanitize_string(12345)
        assert result == "12345"

    def test_normal_string_unchanged(self):
        """Normal text passes through without modification."""
        result = sanitize_string("Hello, I need directions to Gate A")
        assert result == "Hello, I need directions to Gate A"

    def test_ampersand_escaped(self):
        """Ampersand characters are HTML-escaped."""
        result = sanitize_string("tom & jerry")
        assert "&amp;" in result

    def test_quotes_escaped(self):
        """Double quotes are escaped."""
        result = sanitize_string('say "hello"')
        assert '"' not in result or "&quot;" in result


# ===========================================================================
# Input Validation — is_valid_id
# ===========================================================================


class TestIsValidId:
    """Tests for ID format validation."""

    def test_valid_alphanumeric_id(self):
        """Simple alphanumeric ID passes validation."""
        assert is_valid_id("v001") is True

    def test_valid_id_with_underscore(self):
        """ID with underscore passes validation."""
        assert is_valid_id("vol_001") is True

    def test_valid_id_with_hyphen(self):
        """ID with hyphen passes validation."""
        assert is_valid_id("inc-001") is True

    def test_invalid_id_with_space(self):
        """ID with space fails validation."""
        assert is_valid_id("bad id") is False

    def test_invalid_id_with_special_chars(self):
        """ID with special characters fails validation."""
        assert is_valid_id("id<script>") is False

    def test_empty_string_invalid(self):
        """Empty string fails validation."""
        assert is_valid_id("") is False

    def test_too_long_id_invalid(self):
        """ID longer than 64 characters fails validation."""
        long_id = "a" * 65
        assert is_valid_id(long_id) is False

    def test_valid_max_length_id(self):
        """ID of exactly 64 characters passes validation."""
        max_id = "a" * 64
        assert is_valid_id(max_id) is True


# ===========================================================================
# Input Validation — require_fields
# ===========================================================================


class TestRequireFields:
    """Tests for required field validation helper."""

    def test_all_fields_present_returns_none(self):
        """Returns None when all required fields are present."""
        data = {"name": "Alice", "role": "fan", "venue": "v001"}
        result = require_fields(data, "name", "role", "venue")
        assert result is None

    def test_missing_field_returns_field_name(self):
        """Returns the name of the first missing field."""
        data = {"name": "Alice"}
        result = require_fields(data, "name", "role")
        assert result == "role"

    def test_empty_field_value_treated_as_missing(self):
        """Empty string field is treated as missing."""
        data = {"name": "Alice", "role": ""}
        result = require_fields(data, "name", "role")
        assert result == "role"

    def test_no_required_fields_returns_none(self):
        """No required fields always returns None."""
        result = require_fields({"any": "value"})
        assert result is None

    def test_none_value_treated_as_missing(self):
        """None value for a field is treated as missing."""
        data = {"name": None}
        result = require_fields(data, "name")
        assert result == "name"


# ===========================================================================
# Role Selection — XSS / Injection Attempts
# ===========================================================================


class TestRoleSelectionInjection:
    """Role selection must reject injection attempts."""

    def test_html_injection_in_role_rejected(self, client):
        """HTML tags in role field return 400."""
        resp = client.post(
            "/select-role",
            data={"role": "<script>alert(1)</script>"},
        )
        assert resp.status_code == 400

    def test_sql_injection_in_role_rejected(self, client):
        """SQL injection attempt in role field returns 400."""
        resp = client.post(
            "/select-role",
            data={"role": "'; DROP TABLE users; --"},
        )
        assert resp.status_code == 400

    def test_path_traversal_in_role_rejected(self, client):
        """Path traversal attempt in role field returns 400."""
        resp = client.post(
            "/select-role",
            data={"role": "../../etc/passwd"},
        )
        assert resp.status_code == 400


# ===========================================================================
# Error Response Structure
# ===========================================================================


class TestErrorResponseStructure:
    """Error responses must conform to the standard API schema."""

    def test_api_403_error_structure(self, client):
        """403 error response has correct structure."""
        resp = client.get("/fan/api/fan/matches")
        data = resp.get_json()
        assert "success" in data
        assert "errors" in data
        assert data["success"] is False
        assert isinstance(data["errors"], list)
        assert len(data["errors"]) > 0

    def test_error_object_has_code_and_message(self, client):
        """Each error object has 'code' and 'message' fields."""
        resp = client.get("/fan/api/fan/matches")
        data = resp.get_json()
        error_obj = data["errors"][0]
        assert "code" in error_obj
        assert "message" in error_obj

    def test_404_api_error_structure(self, fan_client):
        """404 error from API has correct structure."""
        resp = fan_client.get("/fan/api/fan/matches/nonexistent_xyz")
        data = resp.get_json()
        assert data["success"] is False
        assert resp.status_code == 404

    def test_400_validation_error_structure(self, fan_client):
        """400 validation error has correct structure."""
        import json

        resp = fan_client.post(
            "/fan/api/fan/chat",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is False
        assert resp.status_code == 400
        assert isinstance(data["errors"], list)
