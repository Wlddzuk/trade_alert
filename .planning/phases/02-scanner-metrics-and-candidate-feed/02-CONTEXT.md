# Phase 2: Scanner Metrics and Candidate Feed - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce operator-usable scanner rows and live candidate-feed behavior for US-equity news-driven movers using the trusted provider, runtime, and universe foundation from Phase 1.

This phase clarifies how candidates are represented and surfaced. It does not lock strategy-validity rules, score/rank modeling, Telegram workflow behavior, or paper-trade execution.

</domain>

<decisions>
## Implementation Decisions

### Candidate row identity and catalyst mapping
- The live candidate feed should use one active row per symbol, not one row per headline.
- The row should display the latest related headline for that symbol.
- `time since news` should be measured from the latest related headline/update shown on the row.
- The catalyst tag/classification should follow the latest displayed headline so the row remains internally consistent.

### Candidate row lifecycle
- A symbol should first appear only when the core Phase 2 row fields are ready:
  - headline
  - time since news
  - price
  - volume
  - move context
- The live feed should keep one current row per symbol and refresh that row in place as values change.
- Active rows should expire after a configurable inactivity window rather than staying visible for the entire session by default.
- Premarket rows may carry through the 09:30 ET open if they remain active and trusted.

### Feed ordering before Phase 3 scoring
- Before Phase 3 score/rank exists, the live feed should sort primarily by freshest news first.
- If rows are similarly fresh, `% move on day` should break ties.
- The feed should live-resort automatically as rows update.
- The feed should remain one unified live feed across premarket and regular session rather than splitting into separate ordered sections.

### Strategy inspiration that should shape Phase 2 inputs only
- Phase 2 should prepare enough market/news context for later configurable defaults built around obvious movers:
  - fresh news catalyst
  - strong % move on the day
  - high relative volume
  - price range and liquidity filters
- Minimal strategy context is preferred:
  - 9 EMA
  - 20 EMA
  - 200 EMA
  - VWAP
  - volume
  - MACD only as an optional confirmation input later
- Phase 2 should not convert the pullback-entry, invalidation, or exit ideas into hard rules yet.

### Claude's Discretion
- Exact inactivity timeout defaults for expiring live rows.
- Exact row density, truncation, and text formatting so long as the required fields remain operator-readable.
- Whether the system keeps an internal row-change history behind a single live visible row.
- How partially unavailable non-core fields are displayed, provided core row visibility rules stay intact and later phases can still use the feed.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/providers/models.py`
  - `MarketSnapshot`, `NewsEvent`, `ProviderBatch`, and `CatalystTag` already define the normalized market/news records that Phase 2 should build on.
- `backend/app/ingest/market_ingestor.py`
  - Provides the normalized market-data pull boundary for scanner metrics.
- `backend/app/ingest/news_ingestor.py`
  - Provides the normalized recent-news pull boundary for catalyst attachment and time-since-news logic.
- `backend/app/universe/reference_data.py`
  - Exposes the eligible symbol set that Phase 2 candidate generation should stay inside.
- `backend/app/ops/degraded_state.py`
  - Provides the actionable trust gate that should suppress new candidate surfacing when feeds are degraded.

### Established Patterns
- Vendor payloads are normalized immediately behind provider adapters; downstream scanner logic should consume only internal models.
- Runtime behavior is already anchored to ET session semantics with UTC-safe internals.
- Universe eligibility fails closed and should remain the first gate before feature calculation.
- Provider trust is explicit and actionable; candidate feed behavior should respect that gate instead of silently surfacing rows during stale-feed periods.

### Integration Points
- Phase 2 should assemble scanner rows from normalized `MarketSnapshot` and `NewsEvent` inputs rather than from raw provider payloads.
- Candidate generation should start from the eligible Phase 1 universe, not from ad hoc symbol discovery.
- The live feed should be driven only when the provider trust monitor reports actionable trust.
- Phase 2 outputs must be shaped so Phase 3 can later add `setup_valid`, invalidations, and score/rank without replacing the row identity model chosen here.

</code_context>

<specifics>
## Specific Ideas

- Use the trading ideas only as planning inspiration, not as hard rules in this phase.
- Keep the indicator set minimal and configurable later: `9 EMA`, `20 EMA`, `200 EMA`, `VWAP`, `volume`, with `MACD` optional.
- Keep the candidate feed focused on obvious movers rather than broad market coverage.
- Preserve later optionality for pullback-based entry logic built around:
  - strong initial move
  - pullback
  - first break of the prior candle high after the pullback
- Preserve later optionality for pullback-quality and exit-response defaults built around:
  - lighter selling volume on the pullback
  - broken momentum invalidating the setup
  - weak follow-through or disappearing buyers triggering responsive exit behavior

</specifics>

<deferred>
## Deferred Ideas

- Locking hard pullback-entry rules belongs in Phase 3, not Phase 2.
- Locking momentum-failure invalidation rules belongs in Phase 3, not Phase 2.
- Locking weak-follow-through and buyer-disappearance exit behavior belongs in Phase 4, not Phase 2.
- Formal score/rank modeling still belongs in Phase 3 even though Phase 2 now has a provisional live-feed ordering.

</deferred>

---

*Phase: 02-scanner-metrics-and-candidate-feed*
*Context gathered: 2026-03-14*
