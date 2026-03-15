# Phase 3: Strategy Validity and Ranking - Research

**Researched:** 2026-03-15
**Domain:** momentum-pullback setup validity, trigger/invalidation logic, and ranking for a scanner-first US-equity trading system
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 3 turns the existing candidate feed into a strategy-specific scanner without adding Telegram workflow, paper execution, or exit management.
- `setup_valid` stays a boolean in v1, but invalid rows must expose a primary invalid reason.
- Catalyst freshness for validity is anchored to the first headline in the active catalyst cluster, not the latest displayed update.
- Minimum hard context for validity is:
  - price above `VWAP`
  - `9 EMA > 20 EMA`
- `200 EMA` and `MACD` are not hard gates in v1.
- Pullback volume quality is a soft preference, not a hard validity gate.
- Starting configurable defaults remain:
  - catalyst age `90 minutes`
  - move on day `8%`
  - daily RVOL `2.0x`
  - short-term RVOL `1.5x`
  - pullback retracement `35% to 60%`
- Trigger fires on the first intrabar break above the prior candle high after a valid pullback.
- Trigger timeframe is `15-second` preferred, with `1-minute` fallback.
- Bullish trigger-candle confirmation improves score/context but is not a hard trigger gate.
- Broken momentum invalidates the setup when the pullback low breaks or price loses key intraday context (`VWAP` and `20 EMA`) before trigger.
- After two visible failed breakout attempts, the current move is dead for v1.
- Score is numeric on a `0-100` scale, quality-first, with valid rows above invalid ones.
- Invalid rows remain visible for context with their primary invalid reason shown.
- Strategy explanation uses one primary stage tag plus supporting reasons.

### Claude's Discretion
- Exact score weighting.
- Exact invalid-reason taxonomy.
- Exact stage-tag wording and supporting-reason copy.
- Whether `200 EMA` appears as context on Phase 3 outputs without becoming a hard gate.

### Deferred Ideas (OUT OF SCOPE)
- Exit-response logic like weak follow-through or buyer disappearance belongs in Phase 4.
- Spread, liquidity, stop-distance, and cutoff-time trade rejections remain Phase 4 risk gates.
- Live execution and venue-specific order behavior remain outside v1.
- Turning pullback volume, `200 EMA`, or `MACD` into hard gates is deferred.

</user_constraints>

<research_summary>
## Summary

Phase 3 should not rewrite the Phase 2 scanner pipeline. It should add a strategy-state layer on top of the existing symbol-centric candidate feed: evaluate setup validity, derive trigger eligibility and invalidation state, then compute a score and stage explanation that replace the provisional Phase 2 ordering.

Three planning realities matter:

1. The existing Phase 2 row and feed contracts are stable and should stay stable.
   Strategy logic should decorate or derive from `CandidateRow` rather than turning Phase 2 into a strategy layer retroactively.

2. First-headline catalyst freshness is possible with the current linked-news model.
   `LinkedNewsEvent.related_events` already preserves all related headlines, so Phase 3 does not need to go back to raw Benzinga payloads to find the earliest catalyst timestamp.

3. The preferred trigger timeframe exposes a real data-shape gap.
   The current normalized intraday-bar path is minute-based (`interval_minutes`), while the product decision prefers `15-second` trigger logic. The plan must explicitly decide how to model sub-minute trigger bars or cleanly fall back to `1-minute` when only minute-resolution data is available.

**Primary recommendation:** Keep the roadmap split as three plans:
- `03-01` strategy defaults, context indicators, and setup-valid evaluation
- `03-02` trigger-timeframe handling plus invalidation rules
- `03-03` score/rank and stage-tag output on the live candidate feed

</research_summary>

<architecture_patterns>
## Phase Architecture Guidance

### 1. Add a strategy-state layer, not a Phase 2 rewrite

Phase 2 already established:
- `CandidateRow` as the scanner row contract
- symbol-keyed live feed identity
- trust-aware refresh behavior
- generic `why_surfaced` output

Phase 3 should preserve those contracts and add strategy semantics above them.

Planning implication:
- prefer a new strategy-state record or a derived row model over mutating Phase 2 responsibilities
- keep setup validity, invalid reason, score, and stage explanation grouped together as one strategy layer
- avoid pushing strategy-only concepts down into `metrics.py` or `feed_store.py`

Useful shapes for planning:
- `SetupValidity` or equivalent:
  - `setup_valid: bool`
  - `primary_invalid_reason: str | enum | None`
  - `evaluated_at`
- `TriggerState` or equivalent:
  - `trigger_ready`
  - `triggered_at`
  - `trigger_price`
  - `trigger_timeframe`
- `RankingState` or equivalent:
  - `score_0_to_100`
  - `stage_tag`
  - `supporting_reasons`

The key is separation of concerns: Phase 2 remains “what is the candidate row,” Phase 3 becomes “what is the strategy state of that row right now.”

### 2. First-headline freshness can be computed from current linked-news data

`LinkedNewsEvent` already includes:
- `latest_event`
- `latest_event_at`
- `related_events`

Research implication:
- first-headline freshness can be derived from `min(news_timestamp(event) for event in related_events)`
- Phase 3 does not need a new provider call or raw news-payload access for this rule
- planning should add an explicit helper so row display semantics (latest headline) stay separate from validity freshness semantics (first headline)

Guardrail:
- do not replace the displayed row timestamp semantics from Phase 2
- keep “latest displayed headline” and “first catalyst timestamp for validity” as two separate concepts

### 3. Phase 3 needs explicit intraday context features beyond current Phase 2 metrics

The current code already provides:
- `VWAP` from `MarketSnapshot`
- move and RVOL metrics
- pullback % from high of day

But Phase 3 still needs:
- `9 EMA`
- `20 EMA`
- pullback low tracking
- breakout-attempt counting
- trigger-timeframe bar comparisons

Planning implication:
- add a dedicated intraday context/feature layer instead of overloading `build_market_metrics()`
- keep EMA and pullback-structure calculations testable and deterministic
- model breakout attempts explicitly rather than inferring them ad hoc inside scoring

Recommended feature groups:
- context indicators
  - latest `VWAP`
  - `9 EMA`
  - `20 EMA`
  - optional `200 EMA` context if surfaced read-only
- structure tracking
  - impulse high / high of day reference
  - pullback low
  - retracement ratio against the impulse leg or the chosen default basis
- breakout behavior
  - prior trigger-bar high
  - count of failed breakout attempts
  - current trigger candidate status

### 4. The trigger-timeframe preference creates a data-model gap that the plan must address directly

Current normalized intraday bars are modeled as:
- `IntradayBar`
- `interval_minutes: int`
- Polygon aggregate history path `/range/{interval_minutes}/minute/...`

That cleanly supports `1-minute` and `5-minute`, but not `15-second` as currently modeled.

Planning implication:
- Phase 3 must explicitly decide how sub-minute trigger data enters the system
- the plan cannot assume the current minute-based model already satisfies the trigger requirement

At planning time, the important choices are:
- extend the normalized bar model to support seconds-based intervals, or
- introduce a separate trigger-bar model/policy, or
- implement a clean runtime fallback that uses `1-minute` whenever sub-minute trigger bars are unavailable

The user has already chosen the product rule:
- prefer `15-second`
- fall back to `1-minute`

So the plan should encode that as a first-class runtime policy rather than leaving it as a comment.

### 5. Setup-valid evaluation should be fail-closed and reason-first

Because invalid rows remain visible, the strategy layer needs a stable primary reason when validity fails.

Planning implication:
- validity should evaluate as a clear ordered rule set rather than a loose bag of booleans
- one dominant invalid reason should always be produced when `setup_valid == false`
- score should never override invalidity

Recommended evaluation order:
1. catalyst freshness and contradiction/retraction checks
2. hard move and RVOL thresholds
3. context checks (`VWAP`, `9 EMA`, `20 EMA`)
4. pullback-depth validity
5. broken-momentum checks
6. breakout-attempt exhaustion

This order matters because it gives the operator one interpretable reason rather than six competing failure notes.

### 6. Ranking should replace provisional feed ordering only after validity exists

Phase 2 ordering is intentionally provisional:
- freshest news first
- `% move on day` tie-break

Phase 3 should supersede that with the chosen quality-first score, but should still preserve a clear visibility policy:
- valid rows first
- invalid rows below
- invalid rows still visible

Planning implication:
- treat ranking as a two-level sort:
  1. validity bucket
  2. quality score
- keep stage tagging and supporting reasons close to score generation so explanations stay coherent
- avoid hidden re-sorts split across `feed_service.py` and multiple ranking helpers

### 7. Pullback-volume quality belongs in scoring, not validity

The user explicitly chose lighter selling volume on the pullback as a soft preference.

Planning implication:
- do not block `setup_valid` solely because pullback volume is heavy
- if pullback-volume quality is computed in Phase 3, it should act as:
  - a score boost or penalty
  - a supporting reason in row explanation
- it should not become a separate invalid reason in v1

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Strategy state | Ad hoc booleans added across row builder and feed service | one strategy-state layer or derived row model | Keeps validity, trigger, and ranking cohesive |
| First-headline freshness | new raw-news fetch path | helper over `LinkedNewsEvent.related_events` | The current linked-news model already contains the needed history |
| Invalidity messaging | unordered list of failure flags | ordered primary invalid-reason selection | Matches the user decision that invalid rows stay visible and interpretable |
| Trigger fallback | silent best-effort use of whatever bar exists | explicit `15s` preferred / `1m` fallback policy | Makes the product rule testable and auditable |
| Ranking | score mixed into provisional feed ordering helpers | dedicated score plus stage-tag output | Prevents Phase 2 ordering logic from becoming accidental strategy logic |

**Key insight:** Phase 3 should hand-roll the fewest possible new abstractions, but it must not hide strategy decisions inside Phase 2 feed code.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Using latest displayed headline age for validity
**What goes wrong:** Small follow-up headlines keep resetting freshness and artificially extend setup life.
**Why it happens:** Phase 2 deliberately uses the latest headline for display semantics.
**How to avoid:** Add a dedicated first-catalyst timestamp helper for validity while preserving latest-headline display.
**Warning signs:** `latest_news_at` is reused everywhere without a separate first-headline concept.

### Pitfall 2: Treating current minute-based bars as if they already support `15-second` triggers
**What goes wrong:** Plans promise the preferred trigger timeframe but only implement minute bars.
**Why it happens:** The current code already has `IntradayBar`, so it looks like the problem is solved.
**How to avoid:** Make sub-minute trigger support or explicit fallback handling a visible Phase 3 planning item.
**Warning signs:** Plans mention `15-second` triggers without touching data shape, timeframe policy, or verification.

### Pitfall 3: Letting score override invalidity
**What goes wrong:** Invalid rows with strong move/RVOL appear above valid setups.
**Why it happens:** Quality factors can be numerically stronger than the invalidity penalty.
**How to avoid:** Treat validity as a visibility bucket before score ordering.
**Warning signs:** A single composite score is used to mix valid and invalid rows together.

### Pitfall 4: Making soft preferences into hidden hard gates
**What goes wrong:** Pullback-volume quality or bullish confirmation quietly suppresses otherwise valid setups.
**Why it happens:** These signals feel intuitively important and are easy to convert into `if` statements.
**How to avoid:** Keep them explicitly in ranking/supporting-reason logic, not validity or trigger gating.
**Warning signs:** New invalid reasons start mentioning heavy pullback volume or missing bullish candle confirmation.

### Pitfall 5: Spreading strategy logic across too many layers
**What goes wrong:** Metric code, row builder, feed service, and ranking all each hold part of the strategy truth.
**Why it happens:** Phase 2 already has working seams, so it is tempting to append logic wherever data is available.
**How to avoid:** Keep Phase 3 logic concentrated in one strategy module family with clear inputs and outputs.
**Warning signs:** Multiple files each add partial validity or ranking logic with no single evaluation path.

</common_pitfalls>

<validation_architecture>
## Validation Architecture

Phase 3 should keep using the existing pytest backend test foundation, but it needs a new strategy-focused test slice rather than overloading `tests/scanner_feed`.

Recommended validation posture:
- keep using `pytest`
- introduce a dedicated `tests/scanner_strategy` slice for validity, trigger, invalidation, and ranking
- continue using deterministic normalized fixtures rather than live provider calls
- verify both state derivation and ordering behavior with fixed timestamps and bar sequences

Coverage the planner should ensure exists by the end of the phase:
- setup-valid tests
  - valid candidate with fresh catalyst, move threshold, RVOL threshold, and `VWAP`/`9 EMA`/`20 EMA` context
  - invalid candidate when catalyst age exceeds max age
  - invalid candidate when move or RVOL thresholds fail
  - invalid candidate when pullback retracement is too shallow/deep relative to the configured range
  - primary invalid reason is deterministic when multiple failure conditions exist
- first-headline freshness tests
  - latest displayed headline differs from the earliest catalyst timestamp
  - validity age uses the first headline in the active cluster
- trigger policy tests
  - `15-second` trigger path when sub-minute bars are available
  - clean fallback to `1-minute` when sub-minute bars are unavailable
  - first intrabar break over prior-candle high produces a trigger
  - bullish candle confirmation changes score/context only, not trigger validity
- invalidation tests
  - pullback-low break invalidates
  - loss of `VWAP` and `20 EMA` invalidates
  - two visible failed breakout attempts kill the current move
  - contradictory/retracted catalyst invalidates
- ranking and visibility tests
  - valid rows always sort above invalid rows
  - score ordering is quality-first within the valid bucket
  - invalid rows still render with a primary invalid reason
  - stage tag and supporting reasons remain coherent with the row state

Recommended commands for planning:
- quick verification command: `cd backend && uv run pytest tests/scanner_strategy -q`
- phase-integrated verification command: `cd backend && uv run pytest tests/scanner_feed tests/scanner_strategy -q`
- full suite command: `cd backend && uv run pytest -q`

Planning note:
- if Phase 3 introduces new timeframe or context-feature helpers, tests for those helpers should be built before ranking logic depends on them
- this phase is still deterministic backend logic; no manual-only verification should be necessary

</validation_architecture>

<planning_recommendations>
## Planning Recommendations

### Recommended plan split

- `03-01` Setup-valid rules and configurable strategy defaults
  - add strategy defaults/config surface
  - add first-headline freshness helper
  - add intraday context features needed for `VWAP`/EMA/pullback validity
  - implement ordered validity evaluation with primary invalid reason

- `03-02` Trigger logic and invalidation handling
  - add trigger-timeframe policy (`15s` preferred, `1m` fallback)
  - add trigger evaluation on first intrabar break above prior-candle high
  - implement broken-momentum, contradictory-news, and failed-breakout invalidation behavior

- `03-03` Score/rank behavior and strategy-stage tagging
  - add quality-first numeric score
  - bucket valid rows above invalid rows
  - add stage tag plus supporting reasons
  - replace provisional Phase 2 ordering with strategy-aware ordering

### Recommended dependency shape

- `03-01` should execute first because both trigger logic and ranking depend on configured validity state and context features
- `03-02` should depend on `03-01`
- `03-03` should depend on both `03-01` and `03-02`

### Why this split works

- It keeps defaults and validity semantics stable before trigger behavior is layered on top.
- It forces the trigger-timeframe gap to be addressed explicitly instead of being hidden inside ranking work.
- It lets ranking consume a complete state model rather than mixing provisional feed ordering with partial validity logic.

</planning_recommendations>
