# 🏟️ StadiumMind AI

> **FIFA World Cup 2026 — Smart Stadium Operations Challenge**
>
> An AI-powered, role-based command center for real-time crowd management, incident response, volunteer coordination, and fan assistance at live venues.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [Features by Role](#features-by-role)
- [Assumptions & Design Decisions](#assumptions--design-decisions)
- [Accessibility](#accessibility)
- [Future Scope](#future-scope)
- [Screenshots](#screenshots)
- [Live Demo](#live-demo)

---

## Overview

**StadiumMind AI** is a Flask-based web application that provides four distinct role-focused dashboards for FIFA World Cup 2026 stadium operations:

| Role | Purpose |
|------|---------|
| 🎟️ **Fan** | Wayfinding, AI chat assistance, match schedule |
| 📊 **Organizer** | Crowd analytics, report generation, alert broadcast |
| 🧤 **Volunteer** | Task management, AI-guided instructions |
| 🛡️ **Security** | Incident logging, AI classification, command view |

Each role uses the same backend architecture but exposes a focused, context-appropriate interface. The application integrates with Google Gemini AI (or falls back to high-quality mock responses) to power:

- Fan wayfinding and natural language chat
- Crowd density analysis and operational briefings
- Volunteer task guidance
- Incident classification and risk assessment

---

## Architecture

```
stadiumind-ai/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Env-var driven configuration
│   ├── blueprints/           # Route handlers (one per role)
│   │   ├── core.py           # Landing, role selection, health check
│   │   ├── fan.py            # Fan pages + API
│   │   ├── organizer.py      # Organizer pages + API
│   │   ├── volunteer.py      # Volunteer pages + API
│   │   └── security.py       # Security pages + API
│   ├── services/             # Business logic layer
│   │   ├── fan_service.py
│   │   ├── organizer_service.py
│   │   ├── volunteer_service.py
│   │   └── security_service.py
│   ├── repositories/         # Data access layer (JSON files)
│   ├── models/               # Data model classes
│   ├── ai/                   # AI integration layer
│   │   ├── ai_service.py     # Orchestrator for all AI calls
│   │   ├── gemini_client.py  # Google Gemini API wrapper
│   │   ├── decision_engine.py# Operational decision logic
│   │   ├── prompt_manager.py # Prompt template loader
│   │   ├── response_parser.py# AI response normaliser
│   │   ├── cache.py          # TTL-based response cache
│   │   └── prompts/          # Role-specific prompt templates
│   ├── middleware/
│   │   ├── role_guard.py     # Session-based role protection
│   │   ├── error_handler.py  # JSON error responses
│   │   └── request_logger.py # Structured request logging
│   └── utils/                # Shared helpers (response, validators, datetime)
├── data/                     # JSON data store
│   ├── matches.json
│   ├── venues.json
│   ├── crowd.json
│   ├── incidents.json
│   ├── volunteers.json
│   └── tasks.json
├── templates/                # Jinja2 HTML templates
│   ├── base.html             # Shared shell (topbar, footer, CSS/JS)
│   ├── components.html       # Reusable Jinja macros
│   ├── landing.html
│   ├── fan/
│   ├── organizer/
│   ├── volunteer/
│   └── security/
├── static/
│   ├── css/
│   │   ├── tokens.css        # Design system variables
│   │   ├── base.css          # Reset + typography + utilities
│   │   ├── components.css    # UI component library
│   │   ├── layouts.css       # App shell and grid layouts
│   │   ├── animations.css    # Keyframes + animation utilities
│   │   └── frontend.css      # Page-specific glassmorphism styles
│   └── js/
│       └── app.js            # Client-side interactivity (vanilla JS)
├── run.py                    # Development server entry point
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Web framework** | Flask 3.0.3 |
| **AI backend** | Google Gemini 1.5 Flash (`google-generativeai`) |
| **Environment** | `python-dotenv` |
| **Frontend** | Vanilla HTML5 + CSS3 + JavaScript (ES2020) |
| **Typography** | Space Grotesk + Bebas Neue (Google Fonts) |
| **Data** | JSON files (no database required) |
| **Session** | Flask signed cookie sessions |

> **No build step required.** The entire frontend runs as-is — no Node.js, no bundler, no transpilation.

---

## Setup Instructions

### 1. Prerequisites

- Python 3.10 or higher
- A Google Gemini API key (optional — mock mode available)

### 2. Clone and set up environment

```bash
git clone <repo-url>
cd stadiumind-ai

# Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
# Copy the example file
cp .env.example .env
```

Edit `.env`:

```env
# Required for production; a safe default is used for development
SECRET_KEY=your-long-random-secret-key

# Google Gemini AI (optional — app works without it)
GEMINI_API_KEY=your_gemini_api_key_here

# Set to true to run without any API key (uses realistic mock responses)
MOCK_AI=false

# Flask debug mode
FLASK_DEBUG=true
```

> **Running without a Gemini API key?** Set `MOCK_AI=true` in your `.env`. The application will use pre-built mock responses that accurately represent what real AI outputs would look like.

---

## Running the Application

```bash
python run.py
```

The server starts at **http://localhost:5000**

```
🏟️  StadiumMind AI — FIFA World Cup 2026
   Running at: http://localhost:5000
   Debug mode: true
   Mock AI:    false
```

### Health check

```
GET http://localhost:5000/health
→ {"status": "ok", "service": "StadiumMind AI"}
```

---

## Features by Role

### 🎟️ Fan Dashboard (`/fan/`)

| Page | Feature |
|------|---------|
| **Home** | Live match display, quick action cards, match overview |
| **Wayfinding** | AI-powered route guidance with crowd avoidance and accessibility options |
| **Chat** | Natural language assistant — gates, food, seating, accessibility |
| **Schedule** | Full fixture list with live match indicators |

### 📊 Organizer Dashboard (`/organizer/`)

| Page | Feature |
|------|---------|
| **Dashboard** | System status KPIs, venue occupancy overview, alert indicators |
| **Crowd** | Live crowd snapshot by venue — occupancy %, bottleneck zones, flow status |
| **Reports** | AI operational briefing generation + venue-wide alert broadcast |

### 🧤 Volunteer Dashboard (`/volunteer/`)

| Page | Feature |
|------|---------|
| **Console** | Profile card, task preview, zone and skill summary |
| **Tasks** | Full task list with per-task AI guidance generation |

### 🛡️ Security Dashboard (`/security/`)

| Page | Feature |
|------|---------|
| **Command** | Active incident triage with AI classification buttons |
| **Incidents** | Full incident history with severity and status badges |

---

## API Endpoints

All API routes require a valid role session (set by the role selector).

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/health` | Application health check |
| `GET` | `/fan/api/fan/matches` | All matches |
| `POST` | `/fan/api/fan/chat` | Fan AI chat |
| `GET` | `/fan/api/fan/wayfinding` | Route guidance |
| `GET` | `/organizer/api/organizer/crowd/live` | Live crowd snapshot |
| `POST` | `/organizer/api/organizer/reports/generate` | Generate briefing |
| `POST` | `/organizer/api/organizer/alerts/broadcast` | Broadcast alert |
| `GET` | `/volunteer/api/volunteer/tasks` | Volunteer tasks |
| `POST` | `/volunteer/api/volunteer/ai-guidance` | Task AI guidance |
| `GET` | `/security/api/security/incidents` | All incidents |
| `POST` | `/security/api/security/incidents/<id>/classify` | AI incident classification |

---

## Assumptions & Design Decisions

### Data Layer
- All venue, match, crowd, incident, volunteer, and task data is stored in JSON files in `/data/`. This avoids database setup overhead while accurately simulating a live operational context.
- The data is read on each request — no database ORM needed.

### AI Integration
- The application uses Google Gemini 1.5 Flash for all AI calls, managed via a centralised `AIService` and `DecisionEngine`.
- A `TTL-based cache` (configurable via `AI_CACHE_TTL`) prevents redundant API calls for identical inputs.
- When `MOCK_AI=true`, the `GeminiClient` returns realistic pre-built responses so the full application flow is demonstrable without a real API key.

### Authentication
- Role selection sets a session cookie. There is no user database — the role selector is the "login" for this operational prototype.
- In a production deployment, this would be replaced with OAuth or SSO tied to staff credentials.

### UI Architecture
- **Single JS file** (`app.js`): All client-side interactivity is in one vanilla ES2020 IIFE — no frameworks, no build step.
- **CSS design tokens**: All colours, spacing, typography, shadows, and motion are defined as CSS custom properties in `tokens.css`. Changing the theme requires editing one file.
- **Glassmorphism**: All panels use `backdrop-filter: blur()` with semi-transparent backgrounds. Falls back gracefully in browsers that don't support it.

---

## Accessibility

StadiumMind AI is built with WCAG 2.1 AA compliance as a target:

| Feature | Implementation |
|---------|---------------|
| **Skip navigation** | `<a class="skip-link" href="#main-content">` at top of every page |
| **Keyboard navigation** | All interactive elements reachable and operable via keyboard |
| **Focus indicators** | Gold `outline` on `:focus-visible` — visible and distinct |
| **Screen reader labels** | `aria-label`, `aria-labelledby`, `aria-describedby`, `aria-live` throughout |
| **High contrast mode** | Toggled via toolbar; uses `[data-theme="high-contrast"]` CSS override |
| **Reduced motion** | Toggled via toolbar; `html[data-motion="reduced"]` disables all animations |
| **Font scaling** | Toolbar `A− / AA / A+` scales `html { font-size }` via `--font-scale` custom property |
| **Language selector** | Switches UI language between EN, ES, FR, HI via `localStorage` |
| **Color contrast** | All text/background pairs meet WCAG AA minimum 4.5:1 ratio in both default and high-contrast modes |
| **Live regions** | Chat log uses `role="log"` + `aria-live="polite"`; critical alerts use `aria-live="assertive"` |
| **Semantic HTML** | `<main>`, `<header>`, `<footer>`, `<nav>`, `<section>`, `<article>` used correctly throughout |

---

## Future Scope

### Short-term (next sprint)
- [ ] WebSocket real-time push for crowd density updates
- [ ] PWA manifest for offline-capable fan experience
- [ ] Persistent incident history with timestamps and status audit trail
- [ ] Volunteer check-in / check-out tracking

### Medium-term
- [ ] Multi-venue switching within the same session
- [ ] Staff authentication via Google OAuth
- [ ] Exportable PDF operational briefings
- [ ] Native mobile shell (Capacitor or React Native)

### Long-term / Production
- [ ] Replace JSON data store with PostgreSQL + SQLAlchemy
- [ ] Real CCTV integration for computer-vision-based crowd counting
- [ ] Multi-language AI responses (Gemini supports 40+ languages natively)
- [ ] Role-based audit logging to SIEM system
- [ ] Kubernetes deployment with horizontal pod autoscaling

---

## Screenshots

### Landing Page
Role selector with glassmorphism cards.

![Landing Page](screenshots/landing.png)


### Fan Dashboard
Live match information with wayfinding quick actions.

![Fan Dashboard](screenshots/fan-dashboard.png)


### Fan Chat
AI-powered conversation with suggestion chips.

![Fan Chat](screenshots/fan-chat.png)


### Organizer Dashboard
KPI cards and venue occupancy overview.

![Organizer Dashboard](screenshots/organizer-dashboard.png)


### Security Command Center
Active incident triage view.

![Security Command](screenshots/security-command.png)


### Volunteer Tasks
AI-guided task management panel.

![Volunteer Tasks](screenshots/volunteer-tasks.png)

---

## Development

```bash
# Install dev dependencies (linting)
pip install -r requirements-dev.txt

# Run linter
ruff check .

# Run with debug reload
FLASK_DEBUG=true python run.py
```

---

## Live Demo

https://stadiumind-ai.onrender.com

---

## Licence

This project is submitted as a hackathon entry for the **FIFA World Cup 2026 Smart Stadium Operations Challenge**. All code is original.

---

*Built with 🏟️ by the StadiumMind AI team — 2026*
