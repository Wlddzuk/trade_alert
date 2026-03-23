# System Overview: Buy Signal MVP

**Date:** 2026-03-12
**Purpose:** Describe the intended MVP system shape, assumptions, and decision rationale before implementation.

## System Intent

Buy Signal is a venue-agnostic scanning and paper-trading system for news-driven momentum pullback setups in US equities. In v1, the system ingests near-real-time news and market data, calculates scanner metrics and setup validity, sends operator-facing alerts, and manages approved paper trades through a simulated broker layer.

The system is not a live trading engine in v1. Its purpose is to help an operator find, assess, and paper-trade setups consistently while generating a clean audit trail and preserving a path to future execution adapters.

## Operating Model

- Runs on a single cloud VM in Docker containers
- Operates from 04:00 ET to 16:30 ET
- Watches US-listed common stocks on NASDAQ and NYSE with emphasis on small-cap and other news-driven movers
- Uses Telegram as the primary operator channel
- Uses a dashboard as a secondary, read-only surface for status, logs, and trade review
- Requires human approval for entry
- Manages approved paper trades with rule-based exits unless the operator overrides

## Design Principles

- Scanner-first: the scanner must be useful on its own.
- Alerts-first: alerts must be complete enough to drive action.
- Paper-trading-first: v1 validates workflow and signal quality before any live routing.
- Human-controlled entry: every entry stays operator-approved in v1.
- Venue-agnostic core: execution behavior stays behind an adapter boundary.
- Vendor-abstraction first: provider choice must not leak into scanner logic.
- Auditability over opacity: every important decision and event must be reconstructable.

## High-Level Components

### 1. Provider interface layer

- Defines separate abstract interfaces for market data and news
- Decouples scanner and strategy logic from specific vendors
- Allows Polygon.io and Benzinga to be replaced later without reworking the core system

### 2. News ingestion layer

- Uses Benzinga as the initial provider
- Pulls near-real-time news items
- Preserves headline and catalyst classification
- Tracks freshness and contradictory updates

### 3. Market-data ingestion layer

- Uses Polygon.io as the initial provider
- Pulls near-real-time price and volume data
- Supports premarket and intraday calculations
- Supplies the raw inputs for gap, % change, volume, and pullback measurements

### 4. Normalization and feature layer

- Normalizes symbols, timestamps, and feed records
- Applies universe filters:
  - NASDAQ/NYSE common stocks only
  - exclude OTC, ETFs, warrants, preferreds, rights, closed-end funds, and ADRs
  - price between $1.50 and $20.00
  - average daily volume >= 500,000 shares
- Calculates derived fields including:
  - time since news
  - average daily volume
  - relative volume
  - short-term relative volume
  - gap %
  - % change from prior close
  - pullback % from high of day
- Produces a consistent scanner row model

### 5. Strategy and signal layer

- Applies the momentum pullback rule set
- Uses default numeric thresholds that remain configurable
- Detects recent-news movers with strong intraday expansion
- Evaluates pullback retracement in the 35% to 60% default range
- Uses the first break of prior candle high after valid pullback as the default trigger
- Defaults to 15-second trigger data if available, otherwise 1-minute
- Sets `setup_valid`
- Assigns `why surfaced`
- Produces score/rank for prioritization

### 6. Risk and trade-gate layer

- Applies fixed % risk sizing with 1.0% of paper equity as the starting default
- Validates stop requirement
- Uses structure-based stop below pullback low unless ATR-based risk is tighter
- Enforces max daily loss of 3.0% of paper account equity
- Enforces max concurrent positions = 1
- Blocks new entries after 15:30 ET
- Applies 10-minute cooldown after any loss
- Applies 30-minute cooldown after 2 consecutive losses
- Rejects signals with excessive spread, insufficient liquidity, or excessive stop distance

### 7. Alerting and operator layer

- Delivers primary alerts to Telegram
- Includes catalyst, setup status, entry, stop, target, and score/rank
- Captures approve/reject decisions
- Captures stop/target confirmation or adjustment at approval
- Exposes secondary status and review information in the dashboard

### 8. Paper broker layer

- Simulates order acceptance and fills
- Uses configurable slippage, with 5 bps per side as the initial default
- Supports optional partial-fill simulation, off by default in MVP
- Remains abstract so future venue-specific execution models can be introduced without changing scanner, strategy, or risk logic

### 9. Monitoring and audit layer

- Monitors market-data freshness against a 15-second threshold
- Monitors news-feed freshness against a 60-second threshold
- Monitors scanner loop cadence against a 30-second threshold
- Retries alert delivery up to 3 times and marks failure after 3 consecutive failed attempts
- Records paper P&L summaries
- Stores immutable audit logs with UTC timestamps
- Marks the system degraded/untrusted when freshness or delivery thresholds are breached
- Captures errors and operational failures

## High-Level Data Flow

1. Benzinga news and Polygon.io market data are ingested through separate provider interfaces.
2. Universe filters and derived features are applied to the initial US-equity universe.
3. Strategy logic evaluates recent-news movers for momentum pullback conditions using configurable defaults.
4. Invalid signals are filtered out by setup and risk gates.
5. Remaining candidates are ranked and marked with `setup_valid`.
6. Alert payloads are sent to Telegram and reflected in the secondary dashboard.
7. The operator approves or rejects a paper entry.
8. On approval, the system sizes the paper position from fixed % risk using the approved entry and stop.
9. The paper broker simulates the fill and manages exits according to pre-approved rules unless overridden.
10. Trade events, outcomes, and system health signals are written to logs and summaries.

## Assumptions and Decision Rationale

| Decision / Assumption | Rationale | Design consequence |
|---|---|---|
| US equities are the MVP-first market | Narrowing scope improves scanner quality and workflow clarity | Data models and scan logic prioritize equity market structure first |
| Focus on NASDAQ/NYSE small-cap and news-driven movers | This is the highest-fit environment for the intended strategy style | Universe selection and ranking logic should prioritize catalyst-driven movers |
| Polygon.io is the initial market-data provider | Near-real-time US equities coverage is required | Market-data integration is built around a replaceable provider adapter |
| Benzinga is the initial news provider | Fast headline/catalyst coverage is central to the strategy | News ingestion is built around a separate replaceable provider adapter |
| v1 is scanner-first, alerts-first, paper-trading-first | The product must prove signal quality and operator usefulness before live execution | Live execution concerns do not drive initial system complexity |
| Entry approval stays human-controlled | Risk is lower and validation is cleaner with a human in the loop | Unattended entry is excluded from v1 |
| Telegram is the primary operator channel | It matches the intended fast review workflow | Approval and alert UX should optimize for a Telegram-led flow |
| The dashboard is secondary and read-only in v1 | A second control plane would add complexity without improving core validation | Dashboard scope stays status-, log-, and review-oriented |
| Generic simulated broker comes before venue-specific models | Paper workflow can be validated without broker lock-in | Paper execution is its own abstraction boundary |
| Simulated fills need configurable slippage and optional partial fills | Small-cap movers can trade with unstable liquidity | The paper broker cannot assume ideal fills |
| Near-real-time data is required | Scanner usefulness degrades quickly if updates are stale | Feed freshness monitoring is a first-class concern |
| Relative-volume baseline is configurable, with 20-day average as initial default | Baseline may need tuning after paper validation | Relative-volume logic should not hard-code one permanent baseline |
| Optional fields like float and short interest are enhancements, not blockers | Vendor coverage can be expensive or incomplete | Core scanner logic must remain useful without them |
| Single cloud VM plus Docker is enough for MVP | Operational simplicity matters more than distributed scale in v1 | Deployment should favor straightforward restartability and observability |
| Max open positions stays at 1 by default | This keeps operator load and paper-risk analysis simple | Risk and workflow can assume a single active-position posture |

## Venue-Agnostic Boundary

The core system should separate:

- provider interfaces
- market/news ingestion
- feature calculation
- strategy detection
- risk gating
- alerting
- operator decisions
- paper or live execution behavior

Future venue adapters should plug into an execution interface rather than altering scanner or strategy logic. This matters because later phases may target venues such as Hyperliquid as well as UK-accessible brokers or venues for other asset classes. The MVP should not pre-commit to any one of those models.

## Deferred Extension Points

- Venue-specific paper and live execution adapters
- Additional markets and instruments
- Richer catalyst classification and filtering
- Optional advanced scanner metadata such as float and short interest
- More advanced journaling, analytics, and review tooling

## Constraints

- No production live execution in v1
- No requirement for 24/7 runtime in v1
- No dependency on advanced optional fields for launch readiness
- Architecture should support later extension without importing phase 2 concerns into the MVP core
