# Phase 2: Scanner Metrics and Candidate Feed - Research

**Researched:** 2026-03-14
**Domain:** scanner metrics, baseline market history, news-linked candidate rows, and a live operator-facing feed for a scanner-first US-equity trading system
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- The live candidate feed uses one active row per symbol, not one row per headline.
- The row shows the latest related headline, measures `time since news` from that latest update, and updates the catalyst tag to match that latest displayed headline.
- A row appears only once the core row fields are ready, updates in place, expires after a configurable inactivity window, and may carry through the regular open if still active.
- Before Phase 3 score/rank exists, the feed sorts by freshest news first, then `% move on day`, and reorders live in one unified premarket/regular-session feed.
- Phase 2 should only prepare inputs and live-feed behavior. It must not hard-code setup-valid rules, invalidations, score/rank, Telegram workflow, or paper-trading behavior.

### Claude's Discretion
- Exact inactivity timeout defaults.
- Exact row density/truncation and whether lightweight internal change history is retained.
- How non-core partial fields are displayed while later metrics warm up.

### Deferred Ideas (OUT OF SCOPE)
- Hard pullback-entry rules belong in Phase 3.
- Momentum-failure invalidation rules belong in Phase 3.
- Weak-follow-through and buyer-disappearance exit behavior belong in Phase 4.
- Formal score/rank modeling belongs in Phase 3.

</user_constraints>

<research_summary>
## Summary

Phase 2 should convert the trusted Phase 1 inputs into an operator-usable live candidate feed without smuggling Phase 3 strategy logic into the scanner. The two major additions beyond Phase 1 are:

1. a normalized historical-market input surface so the system can calculate daily and time-of-day relative-volume baselines; and
2. a stateful candidate-feed layer that assembles one live row per symbol, updates rows in place, orders them by freshness/move, and expires stale rows.

The phase should remain deliberately strategy-light. It needs to compute the fields that later strategy defaults depend on, but it should not decide whether a candidate is valid, ranked, or actionable beyond Phase 1 trust gating.

**Primary recommendation:** Plan Phase 2 as three focused plans:
- baseline market-history inputs and pure metric calculators
- candidate-row assembly from market/news/metric inputs
- live candidate-feed store with lifecycle, ordering, and trust-aware updates
</research_summary>

<architecture_patterns>
## Phase Architecture Guidance

### 1. Historical bar inputs are a first-class Phase 2 dependency

Phase 1 normalized only the latest market snapshot and recent news. Phase 2 needs historical market context to satisfy:
- `SCAN-02` daily RVOL using a configurable 20-day baseline
- `SCAN-03` short-term RVOL using current 5-minute volume versus the same time-of-day 5-minute baseline over the last 20 trading days

Planning implication:
- add normalized internal market-history records rather than computing baselines from raw provider payloads
- keep the provider boundary vendor-agnostic by extending internal market-data capabilities or adding a dedicated historical-bar service behind the same provider family
- do not bury baseline retrieval logic inside row assembly or feed store code

Recommended normalized record families to add:
- `DailyBar`
  - symbol
  - trading_date
  - open/high/low/close
  - volume
  - provider
  - observed_at_utc
- `IntradayBar`
  - symbol
  - bar_start_utc
  - bar_interval
  - open/high/low/close
  - volume
  - provider

### 2. Scanner metrics should be pure calculations over normalized inputs

Phase 2 should compute and expose the scanner fields without mixing them with feed-state concerns.

Recommended metric families:
- headline and catalyst metadata
  - latest headline
  - latest catalyst tag/classification
  - time since news
- market move context
  - price
  - volume
  - average daily volume
  - gap %
  - % change from prior close
- relative-volume context
  - daily RVOL against configurable 20-day ADV baseline
  - short-term RVOL against same-time-of-day 5-minute baseline across the last 20 trading days
- pullback context
  - pullback % from high of day

Recommended planning posture:
- implement metric calculators as deterministic services or pure functions over normalized records
- keep formulas explicit and testable
- treat pullback-from-HOD in Phase 2 as a simple live scanner field, not as a later impulse-leg retracement decision

### 3. Candidate rows should be symbol-centric live records

The user chose a symbol-centric live feed. Phase 2 should encode that directly:
- one current row per symbol
- latest related headline shown on that row
- latest-news age/timestamp shown on that row
- latest headline also drives the displayed catalyst tag

Planning implication:
- separate raw news-event storage from row presentation semantics
- row assembly should resolve multiple news events into one current symbol view without losing the ability to update as new headlines arrive
- do not duplicate symbol rows just because multiple headlines exist

### 4. Feed ordering and lifecycle should live in a dedicated stateful layer

Metric calculation and feed lifecycle are different concerns.

Recommended feed behaviors for planning:
- row appears when the core row fields are present
- row updates in place as the same symbol evolves
- live ordering uses:
  1. freshest news first
  2. `% move on day` as tie-break
- inactive rows expire after a configurable quiet period
- premarket rows may continue through the open if they remain active

Recommended planning structure:
- keep a `CandidateFeedStore` or equivalent stateful service keyed by symbol
- separate sort-key derivation from Phase 3 score/rank modeling
- keep session carryover logic explicit rather than implicit in cache behavior

### 5. Phase 1 trust gating must remain the top-level feed gate

Phase 1 already established that new actionable scanner output must stop when market-data or news trust is degraded.

Phase 2 planning should ensure:
- candidate updates only run when the Phase 1 trust state is actionable
- feed code consumes `SystemTrustSnapshot`/trust transitions rather than re-deriving health from raw timestamps
- degraded-state UI wording remains out of scope, but feed suppression is not

This avoids a common failure mode where Phase 2 reintroduces silent stale-feed behavior through a “best effort” scanner loop.

### 6. Partial field handling should be fail-soft, not strategy-heavy

The user chose to show rows once core fields are ready, even if some non-core metrics are still warming up. Phase 2 should honor that without weakening the required row contract.

Recommended planning posture:
- define core row fields explicitly
- allow non-core metrics to be missing or marked pending during early appearance if the chosen row model requires it
- keep the row model compatible with later phases that will consume the same feed for strategy logic

Guardrail:
- do not force Phase 2 to solve later strategy thresholds just to decide if a row exists

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative-volume baselines | Ad-hoc rolling averages embedded in the feed loop | explicit baseline calculators over normalized daily/5-minute bar history | Keeps formulas testable and avoids hidden state |
| Row duplication logic | per-headline feed rows | one symbol-keyed current-row model with latest-headline resolution | Matches the user decision and prevents feed spam |
| Strategy ranking | custom score engine in Phase 2 | provisional freshness + `% move` ordering only | Formal score/rank belongs in Phase 3 |
| Pullback validation | impulse-leg or invalidation logic in Phase 2 | simple pullback-from-HOD field only | Keeps Phase 2 scanner-focused |

**Key insight:** Phase 2 should hand-roll the fewest possible product rules beyond row identity, lifecycle, and field calculation.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Assuming Phase 1 already supports historical baselines
**What goes wrong:** Plans jump straight to RVOL calculation without adding normalized historical bar inputs.
**Why it happens:** Phase 1 already solved provider abstraction, so it is easy to assume all required market shapes exist.
**How to avoid:** Make historical bar retrieval and normalized baseline inputs the first plan in Phase 2.
**Warning signs:** Plans mention 20-day RVOL but reference only `MarketSnapshot`.

### Pitfall 2: Letting Phase 3 strategy logic leak into Phase 2
**What goes wrong:** Plans start defining setup-valid or trigger rules while building the scanner feed.
**Why it happens:** The strategy inspiration is vivid and directly adjacent to scanner output.
**How to avoid:** Limit Phase 2 to metrics, row assembly, and feed behavior; defer validity, invalidation, and score/rank explicitly.
**Warning signs:** Plan tasks mention EMA alignment, trigger candles, or invalidations as acceptance gates.

### Pitfall 3: Using per-headline rows instead of the chosen symbol-centric feed
**What goes wrong:** The operator gets multiple rows for the same symbol as headlines stream in.
**Why it happens:** Raw news data is naturally event-centric.
**How to avoid:** Make the symbol-keyed row model explicit in the plan and test duplicate-headline scenarios.
**Warning signs:** Candidate rows are keyed by event ID instead of symbol.

### Pitfall 4: Baking score/rank behavior into feed ordering too early
**What goes wrong:** The “temporary” ordering logic becomes a hidden scoring engine that later conflicts with Phase 3.
**Why it happens:** Freshness, move, and volume all seem like ranking inputs.
**How to avoid:** Keep Phase 2 ordering intentionally simple and label it provisional.
**Warning signs:** Multiple weighted sort rules or composite priority values appear in Phase 2 plans.

</common_pitfalls>

<validation_architecture>
## Validation Architecture

Phase 2 can reuse the Phase 1 pytest foundation. The validation focus should shift from provider boundaries to deterministic metric and feed-state behavior.

Recommended validation posture:
- keep using `pytest`
- add a dedicated scanner-feed test slice
- avoid live provider calls in automated tests
- use canned historical bars, market snapshots, and news events to make baseline and ordering tests deterministic

Coverage the planner should ensure exists by the end of the phase:
- historical market input tests
  - historical daily and 5-minute bar data normalize into internal records
  - baseline retrieval remains provider-agnostic
- metric calculation tests
  - daily RVOL against a configurable 20-day baseline
  - short-term RVOL against same-time-of-day 5-minute history
  - gap %, % change from prior close, and pullback-from-HOD calculations
- candidate row assembly tests
  - one row per symbol
  - latest headline/tag/age semantics
  - required row fields emitted correctly
- feed lifecycle tests
  - update in place
  - freshness-first ordering with `% move` tie-break
  - inactivity expiry
  - carryover across the regular open
  - trust-gated suppression while system trust is not actionable

Recommended testing pattern for planning:
- quick verification command: `cd backend && uv run pytest tests/scanner_feed -q`
- full suite command: `cd backend && uv run pytest -q`
- keep automated verification on every task commit; this phase is mostly deterministic backend logic
</validation_architecture>

<planning_recommendations>
## Planning Recommendations

### Recommended plan split

- `02-01` Add normalized market-history inputs and scanner metric calculators
- `02-02` Build symbol-centric candidate row assembly from market/news/metric inputs
- `02-03` Build the live candidate-feed store with lifecycle, ordering, and trust-aware updates

### Recommended dependency shape

- `02-01` should execute first because later plans depend on historical baselines and metric outputs
- `02-02` should depend on `02-01`
- `02-03` should depend on both `02-01` and `02-02`

### Why this split works

- It isolates the provider/history expansion from operator-facing feed state
- It lets metric formulas be verified independently before feed behavior is layered on top
- It encodes the user’s row-identity and lifecycle decisions without dragging in later strategy rules

</planning_recommendations>
