# MVP Scope: Buy Signal

**Date:** 2026-03-12
**Purpose:** Define the release boundary for the first shippable version.

## MVP Summary

The MVP is a trading scanner and semi-automated signal system for US equities. It is intentionally narrow: scanner-first, alerts-first, paper-trading-first, with human-approved entry and a venue-agnostic core. The purpose of v1 is to validate scanner usefulness, operator workflow, and paper-trade discipline before any live execution work begins.

## In Scope

### Market and universe

- US equities only
- Initial emphasis on NASDAQ/NYSE small-cap and other news-driven movers
- US-listed common stocks on NASDAQ and NYSE only
- Exclude OTC securities, ETFs, warrants, preferreds, rights, closed-end funds, and ADRs
- Same initial universe for premarket and regular-hours scanning
- Hard universe filters:
  - price between $1.50 and $20.00
  - average daily volume >= 500,000 shares
- Market cap not used as a hard filter in v1

### Data providers and scanner inputs

- Polygon.io for market data
- Benzinga for news
- Separate provider abstractions for market data and news
- Near-real-time market-data ingestion
- Near-real-time news ingestion
- Relative-volume baseline configurable, with 20-day average as initial default
- News headline plus simple catalyst tag/classification

### Scanner outputs

- symbol
- news catalyst / headline
- time since news
- price
- volume
- average daily volume
- relative volume (daily)
- short-term relative volume
- gap %
- % change from prior close
- pullback % from high of day
- strategy tag / why surfaced
- setup valid (boolean)
- score/rank

### Strategy defaults

- Recent catalyst required
- Minimum % move on the day: 8%
- Maximum catalyst age: 90 minutes
- Minimum daily relative volume: 2.0x
- Short-term relative-volume definition:
  - current 5-minute volume divided by average 5-minute volume for the same time-of-day over the last 20 trading days
- Minimum short-term relative volume: 1.5x
- Default pullback retracement range: 35% to 60% of the impulse leg
- Trigger rule:
  - first break of prior candle high after a valid pullback
  - bullish confirmation preferred, not required
- Trigger timeframe:
  - 15-second if available
  - otherwise 1-minute

### Invalidation and trade-quality gates

- No fresh catalyst
- News retraction or contradictory update
- Catalyst too old
- Weak relative volume
- Relative-volume deterioration on the pullback
- Broken momentum after the first move
- Trading halt or LULD pause
- Pullback too deep
- Price below key intraday trend context
- Spread or expected slippage too large
- Signal too late in the move
- Repeated failed breakouts already visible

### Operator workflow

- Telegram as the primary operator channel
- Dashboard as a secondary, read-only surface for status, logs, and trade review
- Entry requires explicit operator approval
- Alert includes proposed entry, stop, target, setup status, catalyst, why surfaced, and score/rank
- Operator confirms or adjusts stop and target at approval
- Exits can follow pre-approved rules
- Operator override remains available

### Paper trading defaults

- Generic simulated broker model
- Configurable slippage model
- Initial slippage default: 5 bps per side
- Optional partial-fill simulation
- Partial-fill simulation off by default
- Fixed risk per trade: 1.0% of paper account equity
- Required per-trade stop
- Stop default:
  - structure-based below pullback low
  - use tighter ATR-based stop if ATR-based risk is tighter
- Max daily loss: 3.0% of paper account equity
- Max open positions: 1
- Entry cutoff time: 15:30 ET
- Cooldown after any loss: 10 minutes
- Cooldown after 2 consecutive losses: 30 minutes
- No trade if stop distance is too large
- Maximum acceptable spread: 0.75% of price
- Minimum liquidity guardrail:
  - average daily volume >= 500,000 shares
  - reject if live volume appears abnormally thin at trigger time

### Runtime, monitoring, and records

- Dockerized deployment
- Single cloud VM
- Runtime window: 04:00 ET to 16:30 ET
- After-hours scanning not required in v1
- Market-data freshness threshold: 15 seconds
- News freshness threshold: 60 seconds
- Scanner loop cadence: at least once every 30 seconds
- Alert retry policy:
  - retry up to 3 times
  - mark failure after 3 consecutive failed attempts
- Mark system as degraded/untrusted if freshness or alert-delivery thresholds are breached
- Error logging
- Paper P&L summaries
- Immutable audit logs with UTC timestamps
- End-to-end paper workflow records:
  - signal
  - reason surfaced
  - operator action
  - simulated fill
  - exit
  - result

## Out of Scope

- Live automated execution
- Venue-specific execution adapters
- Hyperliquid or broker-specific order model integration
- Non-US-equity markets in v1
- Options, oil, or multi-asset expansion
- Dashboard as the primary trade-entry control surface
- 24/7 runtime requirement
- Mandatory float, short interest, or supply-proxy enrichment for launch
- Advanced portfolio management beyond the single-position MVP posture
- Full multi-user product surface

## Release Boundary

The MVP is ready when all of the following are true:

- The system can surface ranked news-driven US equity opportunities during the intended operating window.
- Alerts contain enough context for the operator to make entry decisions without switching between multiple tools.
- The operator can approve or reject paper entries and confirm stop/target at the point of approval.
- The system can simulate entries and exits using the configured slippage model.
- Risk gates block obviously low-quality or operationally unsafe paper entries.
- Monitoring can identify stale feeds, failed scanner loops, and failed alert delivery.
- Audit logs are complete enough to reconstruct every paper trade lifecycle.

## Deferred to Later Phases

- Live order routing
- Broker/venue-specific adapters
- Expanded market and instrument coverage
- Optional enrichment fields when vendor coverage improves
- Broader analytics and journaling features beyond the MVP review loop
