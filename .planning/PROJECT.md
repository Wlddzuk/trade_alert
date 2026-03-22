# Buy Signal

## What This Is

Buy Signal is a shipped operator-facing trading scanner and semi-automated signal system for US equities, focused on NASDAQ/NYSE small-cap and other news-driven movers. The v1 product is scanner-first, alerts-first, and paper-trading-first: it ingests near-real-time news and market data, surfaces ranked momentum pullback setups, sends actionable Telegram alerts, supports human-approved paper trades with full audit logging, and exposes a secondary read-only dashboard for monitoring and review.

The system is intentionally venue-agnostic at the core. Live automated execution and venue-specific adapters are deferred until the scanner, operator workflow, and paper-trading discipline are validated.

## Core Value

Surface high-quality, news-driven momentum pullback opportunities early enough, with enough context and risk structure, that the operator can make faster and more consistent paper-trading decisions.

## Requirements

### Validated

- ✓ Surface ranked news-driven US equity opportunities with near-real-time scanner rows, catalyst context, and quality-first ordering — v1.0
- ✓ Alert the operator in Telegram and keep the entry workflow human-approved in v1 — v1.0
- ✓ Simulate paper entries and exits with configurable slippage, risk controls, and complete lifecycle audit logging — v1.0
- ✓ Keep the system trustworthy during premarket and market hours through degraded-state handling, operator monitoring, and read-only review surfaces — v1.0

### Active

- [ ] Validate v1.0 operator workflow quality on real trading days and capture review-driven refinements.
- [ ] Decide the next execution milestone boundary for venue-specific adapters and live-mode progression after paper validation.
- [ ] Evaluate optional enrichment and market-expansion requirements only after v1.0 workflow quality is proven.

### Out of Scope

- Live automated execution before paper-trading validation data exists.
- Non-US-equity expansion before the US-equity v1 workflow is proven in use.
- Dashboard as the primary control surface while Telegram remains the intended operator path.
- Mandatory enrichment fields as a prerequisite for the next milestone.

## Current State

- Shipped milestone: v1.0 Buy Signal MVP on 2026-03-22
- Archived planning artifacts: `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`, `.planning/milestones/v1.0-MILESTONE-AUDIT.md`
- Current workflow posture: ready to define the next milestone and a fresh requirements set

## Next Milestone Goals

- Turn shipped v1.0 behavior into operator feedback and validation data.
- Decide whether the next milestone should focus on execution adapters, workflow hardening, or signal-quality improvements.
- Keep milestone scope narrow enough that the roadmap can remain evidence-backed and audit-friendly.

## Context

- Strategy inspiration comes from momentum pullback trading on news-driven movers.
- MVP market is US equities first, especially NASDAQ/NYSE small-cap and other news-driven stocks.
- Polygon.io is the chosen market-data provider for v1.
- Benzinga is the chosen news provider for v1.
- The initial scan universe is US-listed common stocks on NASDAQ and NYSE, excluding OTC, ETFs, warrants, preferreds, rights, closed-end funds, and ADRs.
- Runtime target for v1 is premarket plus regular session: 04:00 ET to 16:30 ET.
- The operator is UK-based, so later venue and execution work must preserve optionality for UK-accessible brokers and markets.
- The repo now contains a Python backend implementation, verification artifacts, and archived v1.0 planning history.

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
| US equities are the MVP-first market | Narrow scope improves signal quality and operator focus | ✓ Good |
| Focus on NASDAQ/NYSE small-cap and news-driven movers | Best fit for the intended momentum pullback workflow | ✓ Good |
| Polygon.io is the initial market-data provider | Near-real-time US equities data is required for MVP | ✓ Good |
| Benzinga is the initial news provider | Fast headline and catalyst coverage is central to the strategy | ✓ Good |
| Market data and news stay behind separate provider interfaces | Vendor abstraction matters more than vendor perfection in v1 | ✓ Good |
| Entry approval stays human-controlled | Validate scanner usefulness and paper workflow before any execution automation | ✓ Good |
| Telegram is the primary operator channel | Matches the intended fast review and approval workflow | ✓ Good |
| Dashboard stays secondary and read-only in v1 | Avoid building a second control plane before the core loop works | ✓ Good |
| Generic simulated broker comes before venue-specific execution models | Paper trading can be validated without broker lock-in | ✓ Good |
| Max open positions stays at 1 in MVP | Keeps operator load and paper-risk analysis simple | ✓ Good |

---
*Last updated: 2026-03-22 after v1.0 milestone completion*
