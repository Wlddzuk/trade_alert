# Config Defaults: Buy Signal MVP

**Status:** Recommended initial defaults
**Date:** 2026-03-12
**Purpose:** Record the concrete starting configuration for MVP. All values here are intended to be configurable and subject to tuning after paper-trading results.

## 1. Provider Defaults

- Market data provider: Polygon.io
- News provider: Benzinga
- Provider model:
  - separate provider interfaces for market data and news
  - provider implementations replaceable later without changing core scanner logic
- Fallback posture:
  - if vendor cost or availability becomes a blocker, replace the news feed first or reduce non-critical enrichment
  - float, short interest, and supply proxy remain optional enhancement fields

## 2. Scan Universe Defaults

- Security universe:
  - US-listed common stocks on NASDAQ and NYSE
- Exclusions:
  - OTC
  - ETFs
  - warrants
  - preferreds
  - rights
  - closed-end funds
  - ADRs
- Session coverage:
  - same initial universe for premarket and regular-hours scanning
- Hard filters:
  - price between $1.50 and $20.00
  - average daily volume >= 500,000 shares
- Not a hard filter in v1:
  - market cap

## 3. Strategy Defaults

- Maximum catalyst age: 90 minutes
- Minimum % move on the day: 8%
- Relative-volume baseline:
  - configurable
  - initial daily baseline: 20-day average
- Minimum daily relative volume: 2.0x
- Short-term relative-volume definition:
  - current 5-minute volume divided by average 5-minute volume for the same time-of-day over the last 20 trading days
- Minimum short-term relative volume: 1.5x
- Default pullback retracement range: 35% to 60% of the impulse leg
- Scanner field requirement:
  - pullback % from high of day must be measurable and included in the scanner
- Setup validity posture:
  - setup remains valid only while momentum structure still appears intact

## 4. Trigger Defaults

- Trigger rule:
  - first break of the prior candle high after a valid pullback
- Confirmation:
  - bullish candle confirmation preferred, not required
- Default trigger timeframe:
  - 15-second if available
- Fallback trigger timeframe:
  - 1-minute
- Not required in v1:
  - hammer, engulfing, or other specific named candle patterns

## 5. Risk Defaults

- Fixed risk per trade: 1.0% of paper account equity
- Max daily loss: 3.0% of paper account equity
- Max open positions: 1
- Entry cutoff time: 15:30 ET
- Cooldown after any loss: 10 minutes
- Cooldown after 2 consecutive losses: 30 minutes
- Required stop on every trade: yes
- Stop placement default:
  - structure-based stop below the pullback low
  - if ATR-based risk is tighter, use the tighter stop
- Reject trade if:
  - stop distance is too large for the fixed-risk model
  - liquidity or spread conditions are poor

## 6. Paper-Simulation Defaults

- Slippage model:
  - configurable
  - initial default: 5 bps per side
- Partial-fill simulation:
  - supported by architecture
  - off by default in MVP
- Maximum acceptable spread:
  - 0.75% of price
- Minimum liquidity guardrail:
  - average daily volume >= 500,000 shares
  - live volume must not appear abnormally thin at trigger time

## 7. Runtime Defaults

- Premarket start time: 04:00 ET
- End-of-day stop time: 16:30 ET
- After-hours scanning: not required for v1
- Operating posture:
  - support premarket plus regular session first

## 8. Monitoring Defaults

- Max acceptable age for market-data updates: 15 seconds
- Max acceptable age for news updates: 60 seconds
- Scanner loop completion target: at least once every 30 seconds
- Alert delivery retry policy:
  - retry up to 3 times
  - mark failure after 3 consecutive failed attempts
- Operator safety behavior:
  - if data freshness or alert delivery thresholds are breached, mark system as degraded/untrusted in the operator view

## 9. Tuning Policy

- All defaults in this document are starting values, not permanent truths.
- Thresholds, risk limits, and simulation assumptions should be tuned after reviewing paper-trading outcomes.
- Changes should update this file first so strategy tuning remains explicit and traceable.
