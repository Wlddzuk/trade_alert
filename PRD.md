# PRD: Buy Signal MVP

**Status:** Draft
**Date:** 2026-03-12
**Purpose:** Define the v1 product before implementation.

## Product Summary

Buy Signal is an operator-facing trading scanner and semi-automated signal system for US equities, with emphasis on NASDAQ/NYSE small-cap and other news-driven movers. v1 is explicitly scanner-first, alerts-first, and paper-trading-first: it ingests near-real-time news and market data, surfaces ranked momentum pullback setups, sends actionable alerts, and supports human-approved paper trades with full audit logging.

Live automated execution is out of scope for v1. The core system must remain venue-agnostic so venue-specific adapters can be added in later phases without changing scanner, strategy, or risk logic.

## Problem

News-driven momentum pullback setups appear and decay quickly. A discretionary trader can miss them, enter too late, or lack enough structured context to judge quality consistently. Existing workflows usually split news, scanning, chart review, and trade notes across multiple tools, which increases latency and reduces discipline.

The MVP should reduce that friction. It should give the operator one ranked view of relevant movers, explain why each symbol surfaced, apply trade-quality and risk gates, and support a disciplined paper-trading loop before any live execution work begins.

## Target User

- Primary user is a discretionary trader/operator.
- The user trades news-driven momentum pullback setups in US equities.
- The user wants system assistance with scanning, alerting, and paper-trade management, while keeping final control over entry.

## Core Value

Surface high-quality, news-driven momentum pullback opportunities early enough, with enough context and risk structure, that the operator can make faster and more consistent paper-trading decisions.

## Product Principles

- Scanner-first: the scanner must be useful even before any deeper workflow exists.
- Alerts-first: alerts must carry enough context to support fast decisions.
- Paper-trading-first: v1 validates signal quality and operator workflow before live execution.
- Human-approved entry: the operator remains in control of every entry in v1.
- Venue-agnostic core: execution behavior stays behind an adapter boundary.

## Operator Workflow

1. The system ingests near-real-time news and US equity market data during premarket and market hours.
2. The scanner evaluates the configured US-equity universe for recent-news momentum pullback setups.
3. Each candidate row is tagged with why it surfaced, marked `setup_valid = true/false`, and ranked for operator review.
4. A Telegram alert is sent for qualifying setups with catalyst context, score/rank, proposed entry, proposed stop, proposed target, and current setup status.
5. The operator approves or rejects entry in the Telegram-led workflow. The dashboard is secondary and read-only in v1.
6. On approval, the operator confirms or adjusts stop and target. Position size is derived from fixed % risk using the approved entry and stop.
7. The paper broker simulates fills using configurable slippage and optional partial-fill behavior.
8. Exits follow pre-approved rules unless the operator overrides.
9. The full lifecycle is logged for review, P&L reporting, and auditability.

## Functional Requirements

### 1. Market Focus and Scan Universe

- v1 must optimize for US equities first.
- Initial emphasis is NASDAQ/NYSE small-cap and other news-driven movers.
- The initial scan universe is US-listed common stocks on NASDAQ and NYSE.
- The system must exclude OTC securities, ETFs, warrants, preferreds, rights, closed-end funds, and ADRs unless explicitly enabled later.
- Premarket and regular-hours scanning must use the same initial universe.
- Initial hard universe filters are:
  - price between $1.50 and $20.00
  - average daily volume of at least 500,000 shares
- Market cap is not a hard filter in v1.
- The scanner should prioritize news-driven movers rather than treating the full universe equally.

### 2. Data Providers and Data Requirements

- MVP market data provider is Polygon.io.
- MVP news provider is Benzinga.
- Market data and news must be implemented behind separate abstract provider interfaces so either vendor can be replaced later.
- The system must ingest near-real-time market data for the target US equity universe.
- The system must ingest near-real-time news data suitable for catalyst detection.
- News records must preserve headline plus a simple tag/classification.
- Relative volume must be calculated against a configurable baseline, with 20-day average as the initial default.
- Float, short interest, and supply proxy are enhancement fields and must not block MVP launch.
- If vendor cost or availability becomes a blocker, the system should allow replacement of the news feed or downgrade of non-critical enrichment without changing the core scanner workflow.

### 3. Scanner Output

Each surfaced scanner row must include:

- Symbol
- News catalyst / headline
- Time since news
- Price
- Volume
- Average daily volume
- Relative volume (daily)
- Short-term relative volume
- Gap %
- % change from prior close
- Pullback % from high of day
- Strategy tag / why surfaced
- Setup valid (boolean)
- Score/rank

`Setup valid` means the row currently passes the configured setup logic and is not blocked by an active invalidation or trade-quality gate.

### 4. Strategy Detection

The initial MVP setup is:

- Recent news catalyst
- Strong intraday move
- Elevated relative volume
- Pullback from the impulse leg
- Trigger on first break of the prior candle high after a valid pullback, with bullish candle confirmation preferred but not required

The initial default rule set is:

- maximum catalyst age: 90 minutes
- minimum % move on the day: 8%
- minimum daily relative volume: 2.0x
- short-term relative volume definition: current 5-minute volume divided by average 5-minute volume for the same time-of-day over the last 20 trading days
- minimum short-term relative volume: 1.5x
- default pullback retracement range: 35% to 60% of the impulse leg
- default trigger timeframe: 15-second if available, otherwise 1-minute

All thresholds remain configurable and are starting defaults rather than permanent rules.

### 5. Invalidation and Trade-Quality Gates

The system must suppress or invalidate signals when any of the following are true:

- No fresh news/catalyst
- News retraction or contradictory update
- Too much time elapsed since catalyst
- Weak relative volume
- Relative-volume deterioration during the pullback
- Broken momentum after the first move
- Trading halt or LULD pause
- Pullback too deep
- Price below key intraday trend context
- Spread or expected slippage is too large
- Signal arrives too late in the move
- Repeated failed breakouts are already visible

The exact operational definitions for `broken momentum`, `key intraday trend context`, `signal arrives too late`, and `repeated failed breakouts` still require explicit rule definitions.

### 6. Risk Controls and Paper Simulation

- Paper positions must use fixed % risk sizing.
- Initial fixed risk per trade is 1.0% of paper account equity.
- The system must require a per-trade stop before entry.
- Default stop placement is structure-based below the pullback low, unless ATR-based risk is tighter, in which case the tighter stop is used.
- Max daily loss is 3.0% of paper account equity.
- Max open positions is 1 in MVP.
- The system must block new entries after 15:30 ET.
- Cooldown after any loss is 10 minutes.
- Cooldown after 2 consecutive losses is 30 minutes.
- The system must block trades when stop distance is too large for the fixed-risk model.
- The system must block trades when liquidity or spread conditions are poor.
- The paper broker must support configurable slippage and optional partial-fill simulation.
- Initial slippage default is 5 bps per side.
- Partial-fill simulation is off by default in v1, but must remain available to enable later.
- Maximum acceptable spread is 0.75% of price.
- Minimum liquidity guardrail is average daily volume of at least 500,000 shares, and live volume must not appear abnormally thin at trigger time.

### 7. Alerts and Operator Interaction

- Telegram is the primary operator channel.
- The dashboard is secondary and read-only in v1.
- Email is reserved for system-error notifications.
- Entry requires explicit operator approval in v1.
- The alert must include proposed entry, stop, and target values for operator review.
- The operator confirms or adjusts stop and target at approval.
- Exits may follow pre-approved rules after entry.
- Operator override must remain available at all times.

Each alert must include:

- Reason surfaced
- Catalyst
- Setup status
- Entry
- Stop
- Target
- Score/rank

### 8. Deployment and Monitoring

- MVP runs in Docker containers on a single cloud VM.
- MVP supports premarket scanning plus market-hours workflow.
- Runtime window is 04:00 ET to 16:30 ET.
- After-hours scanning is not required for v1.
- The system must monitor:
  - market-data freshness, with max acceptable age of 15 seconds
  - news-feed freshness, with max acceptable age of 60 seconds
  - scanner loop health, with loop completion at least once every 30 seconds
  - alert delivery success, with up to 3 retry attempts and failure marked after 3 consecutive failed attempts
  - paper P&L summaries
  - immutable audit logs with UTC timestamps
  - error logging
- If data freshness or alert-delivery thresholds are breached, the system must mark itself as degraded/untrusted in the operator view.

### 9. Audit Trail

- The paper workflow must log signal, reason surfaced, operator action, simulated fill, exit, and result.
- The audit trail must support later review of signal quality, operator behavior, and rule performance.

## Success Criteria

The MVP is successful if:

- The operator can rely on one scanner view to identify relevant news-driven US equity movers during the intended operating window.
- Alerts arrive fast enough to support timely review of qualifying setups.
- Each alert explains why the symbol surfaced and whether the setup is currently valid.
- Entry approval remains manual, while post-entry paper management follows defined rules.
- Every approved paper trade is logged end-to-end with enough detail for after-action review.
- Health checks make stale data, scanner failures, and alert-delivery failures visible.
- The design preserves a clean path to later venue adapters without rewriting scanner or strategy logic.

## Non-Goals for v1

- Fully automated live trading
- Venue-specific live execution adapters
- Hyperliquid execution integration
- Multi-market support beyond US equities
- Production broker integration
- Dashboard-led trade control as a required v1 control plane
- 24/7 always-on runtime
- Mandatory float, short interest, or supply-proxy enrichment for launch
- Locking the strategy to one permanent catalyst taxonomy or pattern-heavy candle model before paper validation

## Risks and Constraints

- Polygon.io and Benzinga are chosen for MVP, but vendor quality, cost, or availability could still affect scanner usefulness.
- Thresholds that are too strict may produce too few signals; thresholds that are too loose may reduce signal quality.
- Small-cap news-driven equities can have unstable spreads and halts, which makes realistic fill simulation and risk gating important even in paper mode.
- UK access/compliance matters for later live execution design, but should not distort the v1 US-equities scanner-first scope.

## Later Phases

- Venue-specific execution adapters
- Optional live order routing with human-confirmed or automated execution modes
- Expanded market coverage beyond US equities
- Additional scanner fields such as float, short interest, and supply proxy when vendor coverage is reliable
- Deeper analytics, journaling, and post-trade review tooling
