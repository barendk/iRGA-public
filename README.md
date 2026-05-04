# Goal Review App

A lightweight web application for managing OKR reviews. It provides a structured interface over an existing GitHub Projects board where goals are stored, reducing administrative friction for monthly and quarterly review cycles.

**GitHub remains the source of truth for goals.** This app stores review metadata (PPP updates, confidence scores, reflections) and provides a purpose-built interface for review meetings.

---

## What it does

- **Administrator:** Imports goals from GitHub Projects (via TSV export) using a CLI command, and manages the organizational structure (which teams belong to which domains)
- **Goal owners:** Submit monthly reviews per team — Progress, Problems, Plans, and per-goal confidence scores
- **Meeting facilitator:** Browses the PPP Status dashboard grouped by P-type for efficient meeting facilitation
- **Everyone:** Views goals in list and tree views with filters by period, domain, and level

---

## Prerequisites

**For Docker-based setup (recommended):**
- Docker Engine 24+
- Docker Compose v2

**For local development:**
- Python 3.12
- Node.js 20+ and npm
- PostgreSQL 16 (or use Docker for the database only)

---

## Quick start (Docker)

Clone the repo, then:

```bash
docker-compose up
```

The app starts at **http://localhost:8000**.

To seed the database with sample data on first run:

```bash
SEED_DATA=1 docker-compose up
```

The sample data includes one org, one domain, three teams, and a set of yearly and quarterly goals — enough to explore all views.

---

## Local development setup

```bash
# 1. Create and activate a Python virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Node dependencies and build CSS
npm install
npm run css:build

# 4. Set environment variables (see Configuration section below)
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/goalreview
export APP_SECRET_KEY=dev-secret-key
# Optional: customise organisation branding
# export ORG_NAME="Acme Corp"
# export ORG_TAGLINE="Acme Corp. Building the future."
# export ORG_HEADER="Acme Corporation"

# 5. Apply database migrations
alembic upgrade head

# 6. Seed sample data (optional)
python scripts/seed_dev.py

# 7. Start the development server
uvicorn app.main:app --reload
```

The development server runs at **http://localhost:8000** with automatic reload on code changes.

To rebuild CSS while developing templates:

```bash
npm run css:watch
```

---

## Running tests

```bash
source .venv/bin/activate

# Run all tests
pytest

# Run a specific test file
pytest tests/test_title_parser.py -v

# Run a specific test
pytest tests/test_import_service.py::test_basic_import -v

# Run UI tests (requires Playwright)
playwright install chromium
pytest tests/ui/ -v
```

The test suite uses an in-memory SQLite database for fast unit/integration tests and a live uvicorn server for Playwright UI tests.

---

## Importing goals from GitHub

Goals are imported from a GitHub Projects TSV export.

**Export from GitHub:**
1. Open the GitHub Projects board
2. Export to CSV/TSV (top-right menu → Export)
3. Save as `.tsv`

**Run the import:**

```bash
python -m app.cli import-goals path/to/export.tsv
```

The importer prints a summary of entities created, goals created/updated, parent links set, and any warnings.

**Important:** Goals must follow the title format `<unit> - <period> - <goal text>`, for example:
- `Acme Corp - 2026 - Improve operational excellence` (org, yearly)
- `Engineering - 2026Q1 - Reduce technical debt` (domain, quarterly)
- `Team Alpha - 2026Q1 - Refactor auth module` (team, quarterly)

Rows without the `<unit> - <period>` prefix are treated as structural entity definitions (teams/domains). Import is idempotent: re-running updates existing records matched by GitHub URL.

**Workflow after first import:**
1. Import TSV → entities are created with level `team` by default
2. Open **Admin** → set the correct level (domain/team) for each entity
3. Assign teams to their parent domain
4. Re-import TSV → goals are now linked to correctly classified entities

---

## Configuration

All configuration is via environment variables.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string, e.g. `postgresql://user:pass@host:5432/dbname` |
| `APP_SECRET_KEY` | Yes | — | Secret key for session signing. Use a long random string in production. |
| `ORG_NAME` | No | `My Organisation` | Organisation name shown in page titles, headings, and descriptions. |
| `ORG_TAGLINE` | No | _(empty)_ | Tagline shown in the page footer. Leave empty to hide. |
| `ORG_HEADER` | No | _(empty)_ | Organisation/ministry name shown in the page header. Leave empty to hide. |
| `SEED_DATA` | No | `0` | Set to `1` to load sample data on first container start (when database is empty). |
| `DEBUG` | No | `false` | Set to `true` to enable FastAPI debug mode and detailed error pages. |

Generate a secure secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Operations

### Production deployment

The app is packaged as a Docker image and configured via environment variables. Run it behind a reverse proxy (e.g. nginx) that handles TLS termination. The app listens on port 8000 over plain HTTP.

The app includes `ProxyHeadersMiddleware` which reads `X-Forwarded-Proto` and `X-Forwarded-For` headers from the reverse proxy. This ensures `url_for()` generates correct `https://` URLs for static assets. The reverse proxy must set these headers (nginx does this by default with `proxy_set_header`).

Set production environment variables (see Configuration section) and start in detached mode:

```bash
docker-compose up -d
```

### Database migrations

Migrations run automatically on container start via `entrypoint.sh`. To run manually inside the running container:

```bash
docker-compose exec app alembic upgrade head
```

---

## Architecture overview

```
Browser → reverse proxy (TLS) → FastAPI app (port 8000) → PostgreSQL 16
```

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0
- **Templates:** Jinja2 (server-rendered HTML, no SPA framework)
- **CSS:** Tailwind CSS compiled locally with a custom Rijkshuisstijl theme
- **JavaScript:** Minimal vanilla JS only (no framework)
- **Database:** PostgreSQL 16
- **Containerization:** Docker with multi-stage build (Node.js for CSS, Python for app)

### Security

- **CSRF protection:** Double-submit cookie pattern on all POST routes — no third-party library required
- **Input limits:** PPP text fields capped at 5,000 characters; request body capped at 100 KB
- **Proxy headers:** `X-Forwarded-Proto` trusted for correct HTTPS URL generation behind reverse proxy

### Goal hierarchy

Three organizational levels × two time horizons:

```
Acme Corp (org)
├── Engineering (domain)
│   ├── Team Alpha (team)
│   └── Team Beta (team)
└── Product (domain)
    └── Team Gamma (team)
```

Periods: `2026` (yearly) or `2026Q1` (quarterly).

Two distinct relationship types:
- **Organizational ownership** (`entity_id`): which team/domain owns a goal
- **Goal alignment** (`parent_goal_id`): which higher-level goal this contributes to (optional)

### Monthly reviews

Reviews are submitted **per team** (not per goal). A single review form captures:
- Team-level PPP (Progress, Problems, Plans) — free text
- Support request flag — boolean (combines "need help" + "flag for discussion")
- Per-goal confidence scores (1–10) for each of the team's active goals

Confidence traffic light: 1–3 = red, 4–6 = orange, 7–10 = green.

---

## Project documents

| Document | Contents |
|----------|----------|
| `PRD.md` | Product requirements and user stories |
| `architecture.md` | Technical architecture and data model |
| `Project_context.md` | POC learnings, background, and design decisions |
| `PLAN.md` | Implementation plan with progress tracking |
| `Design documentation/` | Visual mockups (HTML + screenshots) for all 5 views |
| `CLAUDE.md` | Conventions for AI-assisted development |
