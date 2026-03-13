# Stack Research

**Domain:** operator-facing US equity momentum scanner and semi-automated paper-trading system
**Researched:** 2026-03-12
**Confidence:** MEDIUM

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Core backend and data-processing runtime | Strong ecosystem for market-data processing, APIs, async workers, and quantitative logic without overcomplicating MVP delivery. |
| FastAPI | 0.115.x | Backend API and operator-facing services | Good fit for typed APIs, background workflows, and operational simplicity on a single VM. |
| PostgreSQL | 16 | Durable application, audit, and paper-trade storage | Reliable relational core for signals, trade logs, configurations, and review surfaces. |
| Redis | 7.x | Ephemeral state, rate control, queues, and short-lived caches | Useful for scan loops, alert retries, cooldown state, and feed freshness coordination. |
| Next.js | 15.x | Secondary read-only dashboard | Pragmatic React-based operator surface for status, logs, and review without requiring a heavy frontend platform. |
| Docker | 26.x | Packaging and deployment | Matches the single-VM deployment constraint and keeps runtime reproducible. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | 2.x | Strong schema validation for provider payloads and internal models | Use for market/news normalization, scanner rows, and alert payload validation. |
| SQLAlchemy | 2.x | Database access layer | Use for persistent records, audit logs, and review queries. |
| Alembic | 1.x | Schema migrations | Use once persistent storage is introduced. |
| python-telegram-bot | 21.x | Telegram operator alerts and approval flow | Use for the v1 primary operator channel. |
| APScheduler or equivalent lightweight scheduler | 3.x | Session-bound jobs and scan cadence orchestration | Use if a dedicated queue is unnecessary during MVP. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Test runner | Good fit for signal rules, provider adapters, and workflow tests. |
| Ruff | Linting and formatting | Fast feedback for a Python-first codebase. |
| Docker Compose | Local multi-service orchestration | Enough for backend, database, cache, and dashboard during MVP. |

## Installation

```bash
# Backend
uv init
uv add fastapi pydantic sqlalchemy alembic redis python-telegram-bot

# Frontend
npx create-next-app@latest dashboard

# Dev tools
uv add --dev pytest ruff
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI | Django | Use Django if admin-heavy workflows become central and the dashboard grows beyond the current read-only role. |
| PostgreSQL | TimescaleDB | Use TimescaleDB if time-series retention and market-bar analytics become materially heavier than MVP needs. |
| Next.js | HTMX or server-rendered admin UI | Use a lighter UI stack if the dashboard remains extremely narrow and mostly status-driven. |
| Redis-backed lightweight scheduler | Celery or Dramatiq | Use a heavier queue only if scan, alerting, and paper-execution tasks need stronger job isolation. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Broker- or venue-specific logic inside core scanner services | Couples v1 architecture to later execution decisions | Provider and execution adapter boundaries |
| Pattern-heavy trigger logic for MVP | Slows implementation and makes validation harder before paper results exist | Measurable trigger defaults with configurable thresholds |
| Overengineered distributed infrastructure on day one | Adds operational overhead without solving the current single-VM problem | Simple service boundaries plus Docker on one VM |

## Stack Patterns by Variant

**If the dashboard stays read-only and secondary:**
- Keep the backend dominant and the UI thin
- Because the operator workflow is Telegram-led in v1

**If provider fan-out and backfill become more complex later:**
- Introduce a dedicated job queue and more isolated workers
- Because provider retries and recovery logic can outgrow a simple scheduler

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.12 | FastAPI 0.115.x | Safe baseline for modern typing and async support |
| FastAPI 0.115.x | Pydantic 2.x | Standard modern pairing |
| SQLAlchemy 2.x | PostgreSQL 16 | Good fit for typed persistence and migrations |
| Next.js 15.x | React 19 | Current mainstream frontend pairing |

## Sources

- https://fastapi.tiangolo.com/ — backend framework documentation
- https://docs.python.org/3/ — Python runtime reference
- https://www.postgresql.org/docs/ — PostgreSQL documentation
- https://redis.io/docs/ — Redis documentation
- https://nextjs.org/docs — dashboard framework documentation
- https://polygon.io/docs — market-data provider documentation
- https://www.benzinga.com/apis/ — news provider documentation
- https://core.telegram.org/bots/api — Telegram Bot API

---
*Stack research for: operator-facing US equity momentum scanner and semi-automated paper-trading system*
*Researched: 2026-03-12*
