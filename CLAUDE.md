# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Goal review application that provides a lightweight "skin" over GitHub Projects where OKRs are stored, reducing friction for monthly and quarterly review cycles. Organisation name and branding are configurable via environment variables (`ORG_NAME`, `ORG_TAGLINE`, `ORG_HEADER`).

**Key principle:** GitHub remains source of truth for goals. This app stores review metadata only.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (Alembic for migrations)
- **Templates:** Jinja2 (server-rendered HTML)
- **Frontend:** Tailwind CSS (local build, Rijkshuisstijl theme), vanilla JS (minimal)
- **Database:** PostgreSQL 16
- **Containerization:** Docker with docker-compose

## Development Commands

```bash
# Run with docker-compose
docker-compose up

# Run migrations
alembic upgrade head

# Run tests
pytest

# Run single test
pytest tests/test_import.py::test_title_parsing -v

# Start dev server (without Docker)
uvicorn app.main:app --reload
```

## Architecture

### Goal Hierarchy

Three organizational levels × two time horizons:
- **Levels:** org → domain (Engineering, Product, etc.) → team
- **Periods:** yearly (2026) or quarterly (2026Q1)

Two distinct relationship types:
1. **Organizational structure** (`entity_id`): Which team/domain owns this goal
2. **Goal alignment** (`parent_goal_id`): Which goal this contributes to (optional)

### GitHub Title Format (Critical)

Goals must follow: `<unit> - <period> - <goal text>`

Examples:
- `Team Alpha - 2026Q1 - Refactor auth module` (goal)
- `Team Alpha` (structural entity, no period = not a goal)

Parser splits on `" - "` (space-dash-space), max 2 splits. Goal text can contain dashes.

### TSV Import (Two-Pass)

Parent issues may appear after children in the export, so import uses:
1. **Pass 1:** Create/update all structural entities and goals (no parent links)
2. **Pass 2:** Link parent relationships using GitHub URLs

### PPP Dashboard Structure

Group by P-type across teams, not by team:
1. Problems section (flagged items highlighted)
2. Progress section (wins)
3. Plans section
4. Confidence section (individual scores + bar chart)

## Data Model

Key tables: `structural_entities`, `goals`, `monthly_reviews`, `goal_confidences`, `quarterly_reviews`, `review_cycles`

- `structural_entities.level`: 'org', 'domain', or 'team'
- `goals.period_type`: 'yearly' or 'quarterly'
- Monthly reviews are **per team** (PPP fields + support request), NOT per goal
- Confidence scores are **per goal** (separate `goal_confidences` table)
- Monthly confidence scale: 1-10 (traffic light: 1-3 red, 4-6 orange, 7-10 green)
- Quarterly score scale: 1-5 (based on KR achievement)
- Quarterly recommendation: finished, continue, change, or drop

## Security

### CSRF Protection
Double-submit cookie pattern via `app/csrf.py` — no third-party library.
- `CSRFTokenMiddleware` sets `csrftoken` cookie and exposes `request.state.csrftoken`
- All POST routes must include: `dependencies=[Depends(verify_csrf)]`
- All POST forms must include: `<input type="hidden" name="csrftoken" value="{{ request.state.csrftoken }}">`
- Token rotates after each successful POST
- Cookie flags: `SameSite=Lax`, `HttpOnly=True`, `Secure=True` in production

### Middleware Stack (order matters)
```python
app.add_middleware(MaxBodySizeMiddleware)       # Reject >100 KB payloads (413)
app.add_middleware(CSRFTokenMiddleware)          # CSRF cookie + token generation
app.add_middleware(ProxyHeadersMiddleware, ...)  # Trust X-Forwarded-Proto from nginx
```

### Input Limits
- PPP text fields: 5,000 characters max (`MAX_PPP_LEN`)
- Request body: 100 KB max (`MaxBodySizeMiddleware`)

### Reverse Proxy
`ProxyHeadersMiddleware` reads `X-Forwarded-Proto` from nginx so `url_for()` generates correct `https://` URLs. Required when running behind TLS-terminating proxy.

## Important Conventions

- Domain names are NOT hardcoded. Query `structural_entities` table for entities with `level='domain'`
- Period format is case-insensitive: `2026Q1` and `2026q1` both valid
- Only Q1-Q4 are valid quarters
- Validation must be server-side (confidence 1-10, quarterly score 1-5)
- Dutch error messages for user-facing validation
- N+1 queries acceptable for MVP (~20 users, 4-8 teams)

### Monthly Review Flow

User selects team + review cycle on `/reviews`. Single form contains:
- Team-level PPP fields (Progress, Problems, Plans)
- Support request checkbox (team-level, combines "need help" + "flag for discussion")
- Per-goal confidence scores (1-10 radio buttons) for each team goal in that period
- Submit saves everything as a batch

## Project Documents

- `PRD.md` - Product requirements and user stories
- `architecture.md` - Technical architecture and data model details
- `Project_context.md` - Background, POC learnings, design decisions
- `PLAN.md` - Current implementation plan with progress tracking
- `Design documentation/` - Visual mockups (screenshots + HTML) for all 5 views
