# Buy Signal

## What This Is

Buy Signal is an operator-facing trading scanner and semi-automated signal system for US equities, focused on NASDAQ/NYSE small-cap and other news-driven movers. The v1 product is scanner-first, alerts-first, and paper-trading-first: it ingests near-real-time news and market data, surfaces ranked momentum pullback setups, sends actionable Telegram alerts, and supports human-approved paper trades with full audit logging.

The system is intentionally venue-agnostic at the core. Live automated execution and venue-specific adapters are deferred until the scanner, operator workflow, and paper-trading discipline are validated.

## Core Value

Surface high-quality, news-driven momentum pullback opportunities early enough, with enough context and risk structure, that the operator can make faster and more consistent paper-trading decisions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Surface ranked news-driven US equity opportunities with near-real-time scanner rows and clear catalyst context.
- [ ] Alert the operator in Telegram and keep the entry workflow human-approved in v1.
- [ ] Simulate paper entries and exits with configurable slippage, clear risk controls, and complete audit logging.
- [ ] Keep the system trustworthy during premarket and market hours through monitoring, degraded-state handling, and operator review surfaces.

### Out of Scope

- Live automated execution in v1 — paper mode must prove signal quality and workflow discipline first.
- Non-US-equity markets in v1 — keeping the market narrow reduces noise and complexity.
- Dashboard as the primary control surface — Telegram-led workflow is the intended v1 operator path.
- Float, short interest, and supply proxy as launch blockers — these are optional enrichment fields, not MVP prerequisites.

## Context

- Strategy inspiration comes from momentum pullback trading on news-driven movers.
- MVP market is US equities first, especially NASDAQ/NYSE small-cap and other news-driven stocks.
- Polygon.io is the chosen market-data provider for v1.
- Benzinga is the chosen news provider for v1.
- The initial scan universe is US-listed common stocks on NASDAQ and NYSE, excluding OTC, ETFs, warrants, preferreds, rights, closed-end funds, and ADRs.
- Runtime target for v1 is premarket plus regular session: 04:00 ET to 16:30 ET.
- The operator is UK-based, so later venue and execution work must preserve optionality for UK-accessible brokers and markets.
- The repo currently contains planning/spec artifacts only. No implementation has started.

## Constraints

- **Market**: US equities first — keep the MVP narrow around the intended trading workflow.
- **Workflow**: Human-approved entry in v1 — no unattended entry execution.
- **Architecture**: Venue-agnostic core with provider and execution abstractions — avoid broker or venue lock-in.
- **Deployment**: Single cloud VM with Docker — optimize for operational simplicity in MVP.
- **Data**: Near-real-time market and news updates required — stale feeds make the scanner untrustworthy.
- **Operations**: Must support premarket plus market hours before considering extended runtime.
- **Product Scope**: Scanner-first, alerts-first, paper-trading-first — defer live execution and broad market expansion.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| US equities are the MVP-first market | Narrow scope improves signal quality and operator focus | — Pending |
| Focus on NASDAQ/NYSE small-cap and news-driven movers | Best fit for the intended momentum pullback workflow | — Pending |
| Polygon.io is the initial market-data provider | Near-real-time US equities data is required for MVP | — Pending |
| Benzinga is the initial news provider | Fast headline and catalyst coverage is central to the strategy | — Pending |
| Market data and news stay behind separate provider interfaces | Vendor abstraction matters more than vendor perfection in v1 | — Pending |
| Entry approval stays human-controlled | Validate scanner usefulness and paper workflow before any execution automation | — Pending |
| Telegram is the primary operator channel | Matches the intended fast review and approval workflow | — Pending |
| Dashboard stays secondary and read-only in v1 | Avoid building a second control plane before the core loop works | — Pending |
| Generic simulated broker comes before venue-specific execution models | Paper trading can be validated without broker lock-in | — Pending |
| Max open positions stays at 1 in MVP | Keeps operator load and paper-risk analysis simple | — Pending |

---
*Last updated: 2026-03-12 after initialization*
