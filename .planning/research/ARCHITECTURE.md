# Architecture Research

**Domain:** operator-facing US equity momentum scanner and semi-automated paper-trading system
**Researched:** 2026-03-12
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                   Operator Interaction Layer                │
├─────────────────────────────────────────────────────────────┤
│  Telegram Alerts/Approvals   Read-only Dashboard           │
├─────────────────────────────────────────────────────────────┤
│                 Strategy and Workflow Layer                │
├─────────────────────────────────────────────────────────────┤
│  Scanner Engine  Risk Gates  Paper Broker  Alert Service   │
├─────────────────────────────────────────────────────────────┤
│                Ingestion and Feature Layer                 │
├─────────────────────────────────────────────────────────────┤
│  News Provider  Market Provider  Normalizer  Metrics       │
├─────────────────────────────────────────────────────────────┤
│                Persistence and Runtime Layer               │
│  PostgreSQL          Redis           Logs/Audit Store       │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Provider interfaces | Abstract external market/news vendors | Adapter classes or service modules |
| Ingestion services | Pull, normalize, and validate provider data | Async tasks or polling workers |
| Feature engine | Calculate scanner metrics and row fields | Deterministic service layer |
| Strategy engine | Evaluate momentum pullback defaults and invalidations | Rule-based signal service |
| Risk gate | Enforce position, timing, and trade-quality checks | Pre-entry validation layer |
| Alert service | Deliver Telegram alerts and retry on failures | Notification service with retry state |
| Paper broker | Simulate fills, exits, and position state | Stateful simulation service |
| Review surface | Show status, logs, and trade outcomes | Thin frontend over backend APIs |

## Recommended Project Structure

```text
backend/
├── app/
│   ├── providers/        # Polygon/Benzinga adapters and interfaces
│   ├── ingest/           # feed polling, normalization, freshness checks
│   ├── scanner/          # metrics, row building, ranking
│   ├── strategy/         # setup defaults, trigger logic, invalidations
│   ├── risk/             # position sizing and trade-quality gates
│   ├── workflow/         # Telegram approvals, paper broker, exits
│   ├── api/              # dashboard/read APIs and health endpoints
│   ├── storage/          # models, queries, migrations
│   └── ops/              # logging, monitoring, degraded-state logic
frontend/
├── app/                  # read-only dashboard routes
└── components/           # status, logs, review UI
infra/
└── docker/               # container definitions and deployment helpers
```

### Structure Rationale

- **providers/** keeps vendor-specific logic isolated from scanner and workflow rules.
- **scanner/** and **strategy/** stay separate so ranking and rules can evolve independently.
- **workflow/** owns operator approvals and paper execution without leaking into ingestion code.
- **ops/** makes degraded-state handling and logging explicit instead of scattering it.

## Architectural Patterns

### Pattern 1: Adapter Boundary

**What:** External vendors are hidden behind explicit interfaces.
**When to use:** Immediately, because vendors are already chosen but intentionally replaceable.
**Trade-offs:** Slightly more upfront design work, but avoids provider lock-in and simplifies testing.

### Pattern 2: Deterministic Signal Pipeline

**What:** Scanner metrics, setup validity, risk gating, and alert payloads flow through a deterministic rule chain.
**When to use:** For strategy-first products where rules need to be auditable and configurable.
**Trade-offs:** Less flexible than learned models, but far better for v1 trust and tuning.

### Pattern 3: Telegram-led Human Approval Loop

**What:** The primary operator workflow happens in Telegram, while the dashboard remains secondary.
**When to use:** When fast operator review matters more than rich UI controls.
**Trade-offs:** The dashboard stays intentionally limited in v1, but the approval path stays clear.

## Data Flow

### Request Flow

```text
Provider Update
    ↓
Ingestion → Normalization → Metrics → Strategy Rules → Risk Gates
    ↓                                            ↓
 Storage/Audit  ←  Alert Payload  ←  Ranked Candidate Rows
                                      ↓
                                 Telegram Alert
                                      ↓
                             Operator Approve/Reject
                                      ↓
                                 Paper Broker
                                      ↓
                              Exit / Result / Audit
```

### Key Data Flows

1. **Feed-to-scanner flow:** Polygon/Benzinga updates become normalized records and scanner metrics.
2. **Scanner-to-alert flow:** Valid ranked candidates become Telegram alerts with proposed trade parameters.
3. **Approval-to-paper flow:** Operator decisions become paper entries, exits, and audit events.
4. **Health-to-operator flow:** Freshness or delivery failures become degraded/untrusted system state.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single operator on one VM | Monolith plus clear service boundaries is enough |
| More providers or higher symbol count | Separate ingestion and scanner workers first |
| Multi-operator or multi-market | Introduce stronger queue isolation and more explicit tenancy boundaries |

### Scaling Priorities

1. **First bottleneck:** Provider polling and scan cadence — separate ingestion from downstream processing.
2. **Second bottleneck:** Audit and review queries — optimize persistence and read paths before broadening scope.

## Anti-Patterns

### Anti-Pattern 1: Provider Logic Leaks Everywhere

**What people do:** Mix Polygon/Benzinga response shapes directly into scanner and workflow logic.
**Why it's wrong:** Replacing vendors later becomes expensive and error-prone.
**Do this instead:** Normalize all provider payloads immediately behind adapter interfaces.

### Anti-Pattern 2: UI-First Workflow Design

**What people do:** Build a rich dashboard before proving the scanner/alert loop.
**Why it's wrong:** It consumes time without validating the core operator behavior.
**Do this instead:** Keep the dashboard narrow and let Telegram drive approvals in v1.

### Anti-Pattern 3: Paper Broker as a Trivial Afterthought

**What people do:** Assume perfect fills and ignore spread or slippage.
**Why it's wrong:** Small-cap news movers can look tradable on paper while being mechanically poor in practice.
**Do this instead:** Model slippage, spread checks, and explicit trade-quality rejection from the start.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Polygon.io | Provider adapter with normalized market-data interface | Keep feed freshness and error handling explicit |
| Benzinga | Provider adapter with normalized news interface | Preserve headline plus catalyst classification |
| Telegram Bot API | Alert and operator-action interface | Retry behavior and delivery failure status matter |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| providers ↔ ingest | adapter interface | Normalize early |
| scanner ↔ strategy | internal API/service calls | Keep metrics and rules separable |
| strategy ↔ risk | internal API/service calls | Risk gates must be explicit and auditable |
| workflow ↔ storage | persistence layer | Trade lifecycle and audit events must be durable |

## Sources

- Official provider docs for Polygon.io and Benzinga
- Telegram Bot API documentation
- Project requirements and operator workflow decisions

---
*Architecture research for: operator-facing US equity momentum scanner and semi-automated paper-trading system*
*Researched: 2026-03-12*
