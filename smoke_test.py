"""Smoke tests for StadiumMind AI — verifies all routes render correctly."""

import json
# Bootstrap MOCK_AI before importing the app
import os
import sys

os.environ["MOCK_AI"] = "true"
os.environ["FLASK_DEBUG"] = "false"
os.environ["SECRET_KEY"] = "smoke-test-secret-key-not-for-production"

try:
    from app import create_app
except Exception as e:
    print(f"FATAL: Could not import app — {e}")
    sys.exit(1)

app = create_app()
app.config["TESTING"] = True

client = app.test_client()

results = []


def check(label, response, expected_status=200, content_check=None):
    ok = response.status_code == expected_status
    if content_check and ok:
        ok = content_check.encode() in response.data
    status = "PASS" if ok else "FAIL"
    results.append((status, label, response.status_code))
    print(f"  [{status}] {label:<52} -> {response.status_code}")


print()
print("=" * 66)
print("  StadiumMind AI — Smoke Test Suite")
print("=" * 66)

# ── Public routes ──────────────────────────────────────────────────
print()
print("Public routes")
print("-" * 40)
check("GET /  (landing page)", client.get("/"), content_check="StadiumMind")
check("GET /health", client.get("/health"), content_check="ok")

# ── Role selection ─────────────────────────────────────────────────
print()
print("Role selection")
print("-" * 40)
for role in ("fan", "organizer", "volunteer", "security"):
    r = client.post("/select-role", data={"role": role}, follow_redirects=False)
    check(f"POST /select-role -> {role}", r, 302)

r = client.post("/select-role", data={"role": "hacker"}, follow_redirects=False)
check("POST /select-role -> invalid role (400)", r, 400)

# ── Fan pages ──────────────────────────────────────────────────────
print()
print("Fan pages")
print("-" * 40)
with client.session_transaction() as sess:
    sess["role"] = "fan"

check("GET /fan/", client.get("/fan/"), content_check="Fan dashboard")
check("GET /fan/schedule", client.get("/fan/schedule"), content_check="Schedule")
check("GET /fan/wayfinding", client.get("/fan/wayfinding"), content_check="Wayfinding")
check("GET /fan/chat", client.get("/fan/chat"), content_check="Fan chat")

# ── Fan API ────────────────────────────────────────────────────────
print()
print("Fan API")
print("-" * 40)
check(
    "GET /fan/api/fan/matches",
    client.get("/fan/api/fan/matches"),
    content_check="matches",
)

r = client.post(
    "/fan/api/fan/chat",
    data=json.dumps({"message": "Where is Gate A?", "venue_id": "v001"}),
    content_type="application/json",
)
check("POST /fan/api/fan/chat", r, content_check="reply")

r = client.get("/fan/api/fan/wayfinding?venue_id=v001&to=Gate+A")
check("GET /fan/api/fan/wayfinding", r, content_check="best_gate")

r = client.get("/fan/api/fan/venue/v001")
check("GET /fan/api/fan/venue/v001", r, content_check="MetLife")

# ── Organizer pages ────────────────────────────────────────────────
print()
print("Organizer pages")
print("-" * 40)
with client.session_transaction() as sess:
    sess["role"] = "organizer"

check("GET /organizer/", client.get("/organizer/"), content_check="Organizer")
check("GET /organizer/crowd", client.get("/organizer/crowd"), content_check="Crowd")
check(
    "GET /organizer/reports", client.get("/organizer/reports"), content_check="Reports"
)

# ── Organizer API ──────────────────────────────────────────────────
print()
print("Organizer API")
print("-" * 40)
r = client.get("/organizer/api/organizer/crowd/live?venue_id=v001")
check("GET /organizer/api/organizer/crowd/live", r, content_check="venues")

r = client.post(
    "/organizer/api/organizer/reports/generate",
    data=json.dumps({"venue_id": "v001"}),
    content_type="application/json",
)
check("POST /organizer/api/organizer/reports/generate", r)

r = client.post(
    "/organizer/api/organizer/alerts/broadcast",
    data=json.dumps(
        {
            "title": "Test",
            "message": "Test msg",
            "priority": "medium",
            "venue_id": "v001",
        }
    ),
    content_type="application/json",
)
check("POST /organizer/api/organizer/alerts/broadcast", r)

# ── Volunteer pages ────────────────────────────────────────────────
print()
print("Volunteer pages")
print("-" * 40)
with client.session_transaction() as sess:
    sess["role"] = "volunteer"

check("GET /volunteer/", client.get("/volunteer/"), content_check="Volunteer")
check("GET /volunteer/tasks", client.get("/volunteer/tasks"), content_check="Tasks")

# ── Volunteer API ──────────────────────────────────────────────────
print()
print("Volunteer API")
print("-" * 40)
r = client.get("/volunteer/api/volunteer/tasks")
check("GET /volunteer/api/volunteer/tasks", r)

r = client.post(
    "/volunteer/api/volunteer/ai-guidance",
    data=json.dumps({"task_id": "t001"}),
    content_type="application/json",
)
check("POST /volunteer/api/volunteer/ai-guidance", r)

# ── Security pages ─────────────────────────────────────────────────
print()
print("Security pages")
print("-" * 40)
with client.session_transaction() as sess:
    sess["role"] = "security"

check("GET /security/", client.get("/security/"), content_check="Security")
check(
    "GET /security/incidents",
    client.get("/security/incidents"),
    content_check="Incident",
)

# ── Security API ───────────────────────────────────────────────────
print()
print("Security API")
print("-" * 40)
r = client.get("/security/api/security/incidents")
check("GET /security/api/security/incidents", r, content_check="incidents")

r = client.post("/security/api/security/incidents/inc001/classify")
check("POST /security/api/security/incidents/inc001/classify", r)

# ── Role guard enforcement ─────────────────────────────────────────
print()
print("Role guard enforcement")
print("-" * 40)
with client.session_transaction() as sess:
    sess.clear()

r = client.get("/fan/", follow_redirects=False)
check("GET /fan/ without session -> 302", r, 302)

r = client.get("/organizer/", follow_redirects=False)
check("GET /organizer/ without session -> 302", r, 302)

r = client.get("/volunteer/", follow_redirects=False)
check("GET /volunteer/ without session -> 302", r, 302)

r = client.get("/security/", follow_redirects=False)
check("GET /security/ without session -> 302", r, 302)

# ── Wrong role cross-access ────────────────────────────────────────
print()
print("Cross-role access enforcement")
print("-" * 40)
with client.session_transaction() as sess:
    sess["role"] = "fan"

r = client.get("/security/", follow_redirects=False)
check("Fan accessing /security/ -> 302 (role guard)", r, 302)

r = client.get("/organizer/", follow_redirects=False)
check("Fan accessing /organizer/ -> 302 (role guard)", r, 302)

# ── Switch role ────────────────────────────────────────────────────
print()
print("Switch role")
print("-" * 40)
check(
    "GET /switch-role -> 302", client.get("/switch-role", follow_redirects=False), 302
)

# ── Summary ────────────────────────────────────────────────────────
print()
print("=" * 66)
passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")
total = len(results)
print(f"  RESULT  PASS: {passed}   FAIL: {failed}   TOTAL: {total}")
print("=" * 66)

if failed:
    print()
    print("FAILURES:")
    for s, label, code in results:
        if s == "FAIL":
            print(f"  [FAIL] {label} -> HTTP {code}")
    sys.exit(1)
else:
    print()
    print("  All smoke tests passed. Application is ready.")
    print()
