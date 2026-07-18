# 🏟️ StadiumMind AI

## PROJECT OVERVIEW

**StadiumMind AI** is an intelligent, AI-powered stadium management command centre designed for the FIFA World Cup 2026. It provides four distinct, role-focused dashboards (Fan, Organizer, Security, and Volunteer) to orchestrate real-time live venue operations. 

**The Real-World Problem:**
Managing massive crowds in 80,000+ capacity stadiums poses critical challenges: congestion bottlenecks, delayed incident responses, unoptimized volunteer deployments, and poor fan navigation. Traditional systems are siloed and reactive.

**AI-Powered Stadium Management Concept:**
StadiumMind AI solves this by unifying data across the venue and applying Google Gemini AI alongside a deterministic Decision Engine. It predicts crowd surges, automatically classifies security incidents, provides smart wayfinding for fans, and generates dynamic task guidance for volunteers. This proactive, AI-first approach ensures safety, efficiency, and an exceptional event experience.

---

## FEATURE REQUIREMENT MAPPING

| Requirement | Implementation | Module/File |
|-------------|---------------|-------------|
| **Fan Experience** | | |
| AI Match Assistant | Natural language chat for stadium queries via Gemini | `app/services/fan_service.py` |
| Crowd Analysis | Crowd status integrated into wayfinding to avoid bottlenecks | `app/ai/decision_engine.py` |
| Route Guidance | Smart gate selection and navigation tips based on live crowd data | `app/blueprints/fan.py` |
| Emergency Alerts | Urgent warnings surfaced during chat or wayfinding | `app/ai/decision_engine.py` |
| **Organizer Operations** | | |
| Resource Allocation | AI analysis of zone density to recommend staff redeployment | `app/services/organizer_service.py` |
| Venue Monitoring | Live dashboard tracking attendance, incidents, and volunteer status | `app/blueprints/organizer.py` |
| Incident Management | Aggregated view of all active security and medical situations | `app/services/organizer_service.py` |
| AI Recommendations | Auto-generated operational briefings detailing priorities | `app/ai/prompts/event_briefing.txt` |
| **Security Operations** | | |
| Threat Detection | Real-time zone heatmap highlighting congestion and bottlenecks | `app/services/security_service.py` |
| Incident Classification | Gemini AI classifies incident type, severity, and needed steps | `app/ai/prompts/incident_classifier.txt` |
| Risk Analysis | AI evaluates incident confidence, resolution time, and resources | `app/blueprints/security.py` |
| Emergency Response | Automated extraction of response protocols based on incident type | `app/constants.py` |
| **Volunteer Coordination** | | |
| Task Assignment | Real-time distribution of tasks to volunteers | `app/services/volunteer_service.py` |
| Priority Management | Tasks sorted automatically by urgent/high/medium/low priority | `app/models/volunteer.py` |
| Escalation Workflow | One-click SOS reporting for immediate command centre escalation | `app/blueprints/volunteer.py` |
| AI Assistance | Step-by-step contextual guidance, safety notes, and fan phrases | `app/ai/prompts/volunteer_guidance.txt` |

---

## ARCHITECTURE SECTION

StadiumMind AI utilizes a clean, modular backend architecture to separate concerns, ensure data integrity, and provide a seamless API for the frontend.

```text
[ Blueprint Layer ]  →  Routes HTTP requests, validates inputs, enforces RBAC.
        ↓
[ Service Layer ]    →  Executes core business logic and orchestrates models.
        ↓
[ AI Decision Engine ]→ Generates deterministic context and AI prompts.
        ↓
[ Repository Layer ] →  Provides atomic CRUD operations and data encapsulation.
        ↓
[ Data Layer ]       →  JSON-backed persistence for venues, crowds, matches, etc.
```

**Responsibilities by Directory:**

* **`app/ai/`**: Central AI orchestrator, deterministic decision engine, Gemini API client, response parser, prompt management, and TTL caching.
* **`app/blueprints/`**: Thin HTTP layer defining REST API endpoints and page routes per persona, decorated with role guards.
* **`app/services/`**: The core business logic layer. Composes repositories and AI tools to produce serializable responses for the blueprints.
* **`app/repositories/`**: Data access layer providing atomic read/write operations against the JSON data store. Maps JSON to domain models.
* **`app/models/`**: Pure domain dataclasses and enums (e.g., `Match`, `Zone`, `Incident`) with zero framework dependencies.
* **`app/middleware/`**: Cross-cutting Flask hooks including Role-Based Access Control (`role_guard.py`), global error handling, and request logging.
* **`app/utils/`**: Shared utilities for API response envelopes, input validation/sanitization, and UTC datetime formatting.

---

## AI SYSTEM DESIGN

* **Decision Engine**: A deterministic system (`app/ai/decision_engine.py`) that builds a structured operational context from real-time venue, crowd, and match data. It guarantees safe operational recommendations (gate selection, navigation, emergency actions) even if the AI fails.
* **Gemini Integration**: A robust wrapper (`app/ai/gemini_client.py`) around Google Gemini 1.5 Flash. It enforces structured JSON outputs and implements exponential backoff retries.
* **Prompt Management**: Template-based prompt loader (`app/ai/prompt_manager.py`) that strictly sandboxes untrusted user input within `<user_input>` XML tags to prevent prompt injection attacks.
* **Response Parser**: Validates all Gemini outputs against expected schema keys and coerces types before returning them to the service layer (`app/ai/response_parser.py`).
* **AI Fallback Handling**: Every AI pipeline intent has a predefined fallback response. If the AI is unreachable, times out, or returns invalid data, the system gracefully degrades to safe, deterministic guidance without throwing HTTP 500s.
* **AI Workflow**: `Cache Lookup` → `Prompt Construction` → `Gemini Call` → `Response Parsing` → `Cache Update` → `Return Data`. 

---

## MODULE RESPONSIBILITIES

| Module | Responsibility |
|--------|---------------|
| `app/__init__.py` | Application factory; configures Flask, registers blueprints, and initializes middleware. |
| `app/config.py` | Environment variable parsing and validation; defines `Config` and `TestConfig`. |
| `app/constants.py` | Single source of truth for all magic numbers, roles, severity thresholds, and hardcoded strings. |
| `app/services/fan_service.py` | Manages fan match schedules, AI chat processing, and smart wayfinding logic. |
| `app/services/organizer_service.py` | Aggregates dashboard metrics, analyzes crowd data, and generates AI event briefings. |
| `app/services/security_service.py` | Handles incident logging, AI threat classification, and heatmap data aggregation. |
| `app/services/volunteer_service.py` | Manages task assignments, priority sorting, SOS escalations, and AI task guidance. |
| `app/repositories/json_base.py` | Abstract base class ensuring thread-safe, atomic file reads and writes for the data layer. |

---

## REQUEST FLOW

**Fan request flow:**
1. User submits question: `"Where is the nearest food court?"`
2. `fan.py` Blueprint validates the required message field and ensures the user holds the `ROLE_FAN` session.
3. `FanService` retrieves live match and venue context.
4. `DecisionEngine` generates a structured context.
5. `ai_service` constructs the prompt using `fan_assistant.txt`, queries Gemini, parses the JSON response, and returns actionable suggestions and reply.

**Security incident flow:**
1. Guard submits incident: `"Large crowd pushing at Gate A."`
2. `security.py` processes the `POST` request.
3. `SecurityService` creates an initial "unclassified" incident in `IncidentRepository`.
4. The classification pipeline calls `ai_service` to evaluate the text.
5. Gemini classifies it as a `high` severity `crowd_surge` and provides mitigation steps.
6. The updated incident is saved and immediately reflected on the Command Centre dashboard.

**Volunteer assignment flow:**
1. Volunteer requests active tasks via the dashboard.
2. `volunteer.py` Blueprint receives the `GET` request.
3. `VolunteerService` fetches all tasks assigned to the volunteer's ID.
4. Tasks are sorted locally by `PRIORITY_ORDER` (Urgent > High > Medium > Low).
5. When a volunteer clicks a task, `ai_service` dynamically generates contextual task guidance, fan-facing phrases, and safety notes.

**Organizer analysis flow:**
1. Organizer clicks "Generate Briefing" on the dashboard.
2. `OrganizerService` pulls all active incidents, live match data, crowd density metrics, and volunteer availability.
3. Data is formatted into an AI context window.
4. `ai_service` processes the data through `event_briefing.txt` using Gemini.
5. A structured operational briefing (with priorities, summaries, and action items) is returned and displayed to the Organizer.

---

## TESTING SECTION

StadiumMind AI maintains robust test coverage to ensure operational reliability:

* **Unit testing**: Comprehensive unit tests covering domain models, enums, response parsers, and prompt managers.
* **API testing**: Integration tests simulating HTTP requests against Blueprints, validating JSON schemas, and enforcing Role-Based Access Control.
* **Smoke testing**: A standalone `smoke_test.py` script validates that all pages render, critical APIs respond correctly, and role guards function properly without requiring the full `pytest` runner.
* **Coverage validation**: The test suite tracks coverage using `pytest-cov`, configured via `.coveragerc` to target strong coverage (≥90%) across all application modules.

---

## CODE QUALITY SECTION

* **Modular architecture**: The codebase strictly adheres to an N-Tier architecture (Blueprints → Services → Repositories), ensuring high cohesion and low coupling.
* **Separation of concerns**: UI rendering is strictly separated from business logic. Data access is completely isolated from HTTP requests.
* **Constants management**: Every magic number, status string, limit, and configuration key is centralized in `app/constants.py`, preventing hardcoded values across modules.
* **Error handling**: A global `error_handler.py` middleware catches exceptions and HTTP errors, logging tracebacks internally while returning standardized, sanitized JSON envelopes (`{success: false, errors: [...]}`) to the client.
* **Reusable services**: `DecisionEngine` and `ai_service` are decoupled utilities consumed uniformly by all persona services, minimizing code duplication.
* **Clean code practices**: Code is strictly typed using Python type hints, formatted uniformly, linted, and logically organized.

---

## DEPLOYMENT SECTION

**Environment configuration:**
Configuration is driven entirely by environment variables. The application reads from `.env` in development and requires standard system environment variables in production. 

**Required environment variables:**
* `SECRET_KEY`: Must be a cryptographically secure random string in production (used for session signing).
* `GEMINI_API_KEY`: Google Gemini API key (can be omitted if `MOCK_AI=true`).
* `MOCK_AI`: Boolean flag to run the application using realistic fallback responses without hitting external APIs.
* `FLASK_DEBUG`: Set to `false` in production.
*(Note: API keys and secrets are NEVER exposed in the codebase or version control. `.env.example` provides a template, while `.env` is omitted from version control.)*

**Production deployment flow:**
1. Clone the repository to the production server.
2. Install production dependencies via `pip install -r requirements.txt`.
3. Configure the production environment variables safely.
4. Launch the application using Gunicorn as the WSGI HTTP server:
   ```bash
   gunicorn "app:create_app()" --workers 4 --bind 0.0.0.0:8000
   ```
5. Configure a reverse proxy (e.g., NGINX) in front of Gunicorn to handle SSL termination, serve static files, and forward requests.
