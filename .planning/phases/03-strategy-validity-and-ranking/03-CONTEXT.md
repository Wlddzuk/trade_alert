# Phase 3: Strategy Validity and Ranking - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the existing candidate feed into a strategy-specific scanner by applying the momentum pullback defaults, defining current setup validity, enforcing trigger and invalidation behavior, and adding score/rank plus strategy-stage explanation.

This phase clarifies how candidates become valid, invalid, trigger-ready, or invalidated. It does not add Telegram delivery, paper execution, exit management, or operator approval behavior.

</domain>

<decisions>
## Implementation Decisions

### Setup validity semantics
- `setup_valid` should remain a boolean in v1.
- When `setup_valid` is false, the system should also attach the primary invalid reason so the row stays interpretable.
- Catalyst freshness for validity should be measured from the first headline in the active catalyst cluster, not from the latest displayed update.
- Minimum hard context for `setup_valid` is:
  - price holds above VWAP
  - `9 EMA` is above `20 EMA`
- `200 EMA` and `MACD` are not hard validity gates in v1.
- Pullback volume quality is a soft preference for ranking and operator context, not a hard validity gate.
- Existing configurable defaults from prior product decisions remain the starting point for Phase 3:
  - max catalyst age `90 minutes`
  - min move on day `8%`
  - min daily RVOL `2.0x`
  - min short-term RVOL `1.5x`
  - default pullback retracement `35% to 60%`

### Trigger and invalidation behavior
- Trigger should fire on the first intrabar trade above the prior candle high after a valid pullback.
- Preferred trigger timeframe remains `15-second`, with `1-minute` fallback when lower-resolution data is unavailable.
- Bullish candle confirmation is preferred but not required; it should act as a score/context boost rather than a hard trigger gate.
- Broken momentum before trigger should invalidate the setup when either of these happens:
  - the pullback low breaks
  - price loses key intraday context, specifically VWAP and `20 EMA`
- After two visible failed breakout attempts, the current move should be treated as dead for v1 instead of recycling repeated triggers.
- The hard invalidation set already chosen in earlier planning remains in force for this phase:
  - contradictory or retracted news
  - catalyst too old by configured age
  - weak relative volume
  - pullback too deep
  - trading halt or LULD pause
  - spread/slippage too large

### Ranking and strategy-stage explanation
- Score should be numeric on a `0-100` scale.
- Row rank should derive from that score.
- Valid setups must rank ahead of invalid ones.
- Invalid rows should remain visible for context, with their primary invalid reason shown.
- Ranking should be a quality-first composite, not a single-factor leaderboard.
- The strongest ranking dimensions should be:
  - valid pullback structure
  - catalyst freshness
  - strength of move on day
  - daily and short-term relative volume
- Pullback volume quality and bullish trigger confirmation may improve score, but should not dominate it.
- Strategy explanation should use:
  - one primary stage tag
  - supporting reasons
- Primary stage tags should reflect setup state, with initial direction such as:
  - `building`
  - `trigger_ready`
  - `invalidated`
- Exact label copy can remain flexible if the stage meaning stays clear.

### Claude's Discretion
- Exact numeric weighting inside the `0-100` score, as long as it stays quality-first and honors the validity gate.
- Exact primary invalid-reason taxonomy and row copy, as long as one dominant reason is always available.
- Exact stage-tag names and supporting-reason wording, as long as they preserve the decided stage semantics.
- Whether `200 EMA` appears as read-only context in Phase 3 outputs, provided it does not become a hard gate.

</decisions>

<specifics>
## Specific Ideas

- Keep indicators minimal and purposeful:
  - hard context uses `VWAP`, `9 EMA`, and `20 EMA`
  - `200 EMA` is context only
  - `MACD` remains optional later confirmation, not a v1 requirement
- Keep the strategy close to obvious news-driven movers and the first clean pullback/re-break, not pattern-heavy candle logic.
- Preserve the Phase 2 row identity:
  - latest related headline still drives what is displayed on the row
  - first headline in the active catalyst cluster drives validity freshness

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/scanner/models.py`
  - `CandidateRow` already carries the scanner row contract and can be extended or decorated with validity, invalid reason, score, and stage information.
  - `LinkedNewsEvent` already retains `related_events`, which makes first-headline catalyst-age logic possible without going back to raw provider payloads.
- `backend/app/scanner/metrics.py`
  - Already computes the Phase 3 inputs for day move, daily RVOL, short-term RVOL, and pullback % from high of day.
- `backend/app/scanner/row_builder.py`
  - Already assembles the current symbol row and generic `why_surfaced` text from normalized inputs.
- `backend/app/scanner/feed_service.py`
  - Already maintains live feed ordering and trust-aware suppression, so Phase 3 should layer strategy logic onto the existing feed rather than replace it.

### Established Patterns
- Scanner layers consume normalized internal models only; no raw Polygon or Benzinga payloads should leak into Phase 3 logic.
- The feed remains symbol-centric and unified across premarket and the regular open.
- Provider trust is already explicit and gates candidate updates before strategy logic runs.
- Phase 2 deliberately kept validity, trigger, and rank logic out of the metric and row layers, leaving clean seams for this phase.

### Integration Points
- Phase 3 should attach `setup_valid`, primary invalid reason, score, and stage explanation to the existing candidate-row/feed flow.
- Trigger logic should consume the existing preferred `15-second` bar stream with `1-minute` fallback, using the same normalized intraday-bar approach established in Phase 2.
- Ranking should replace the provisional freshest-news ordering only after strategy-state outputs exist, without changing the one-row-per-symbol feed identity.

</code_context>

<deferred>
## Deferred Ideas

- Exit-response rules such as weak follow-through or buyer disappearance belong in Phase 4, not this phase.
- Spread, liquidity, stop-distance rejection, and cutoff-time enforcement remain part of Phase 4 risk gating, even if Phase 3 can expose context that later feeds those checks.
- Live execution behavior and venue-specific order models remain outside v1 and outside this phase.
- Making pullback volume quality, `200 EMA`, or `MACD` into hard gates is deferred unless later tuning proves it necessary.

</deferred>

---

*Phase: 03-strategy-validity-and-ranking*
*Context gathered: 2026-03-14*
