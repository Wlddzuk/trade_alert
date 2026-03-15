---
phase: 03-strategy-validity-and-ranking
plan: 02
subsystem: scanner
tags: [python, scanner, triggers, invalidation, pytest]
requires:
  - phase: 03-strategy-validity-and-ranking
    provides: setup-valid contract and strategy defaults
provides:
  - preferred 15-second trigger-bar support with 1-minute fallback
  - first-break trigger evaluation after valid pullback context
  - deterministic invalidation rules for stale catalyst, contradictory news, halt, context loss, and dead moves
affects: [phase-03, phase-04, phase-05]
tech-stack:
  added: []
  patterns: [trigger-timeframe-fallback, first-break-trigger, deterministic-invalidation]
key-files:
  created:
    - backend/app/scanner/trigger_policy.py
    - backend/app/scanner/trigger_logic.py
    - backend/app/scanner/invalidation.py
    - backend/tests/scanner_strategy/test_trigger_logic.py
    - backend/tests/scanner_strategy/test_invalidations.py
  modified:
    - backend/app/providers/models.py
    - backend/app/providers/base.py
    - backend/app/providers/polygon_adapter.py
    - backend/app/scanner/history.py
key-decisions:
  - "Second-based trigger data support was added at the provider boundary rather than by special-casing Polygon payloads inside scanner logic."
  - "The first intrabar break of the prior candle high is the trigger, with bullish confirmation recorded as a preference rather than a hard requirement."
  - "Invalidation stays separate from setup-valid evaluation so an initially valid setup can later become untrusted for a clear reason."
patterns-established:
  - "Trigger-bar selection is isolated behind a policy helper with explicit preferred and fallback paths."
  - "Trigger evaluation and invalidation consume validity/context outputs rather than recomputing core setup rules."
  - "Contradictory catalyst and halt handling are explicit invalidation states, not hidden score penalties."
requirements-completed: [SIG-03, SIG-04]
duration: 2 min
completed: 2026-03-15
---

# Phase 3: Strategy Validity and Ranking Summary

**Preferred 15-second first-break trigger logic with 1-minute fallback and deterministic invalidations for stale catalyst, contradiction, halt, and momentum failure**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T07:26:51Z
- **Completed:** 2026-03-15T07:28:44Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Extended normalized intraday-bar support so trigger evaluation can prefer 15-second data and fall back to 1-minute bars when needed.
- Implemented the first-break trigger rule using the first bar whose high exceeds the prior bar high after a valid pullback.
- Added explicit invalidation decisions for contradictory catalyst updates, stale catalyst age, weak volume, halts, deep pullbacks, pullback-low breaks, lost intraday context, and repeated failed breakouts.

## Task Commits

1. **Task 1: Add trigger timeframe support and fallback selection** - `0defdf4` (feat)
2. **Task 2: Add first-break trigger logic and invalidation rules** - `602a100` (feat)

## Files Created/Modified

- `backend/app/providers/models.py` - second-based intraday-bar support
- `backend/app/providers/base.py` - provider contract support for second or minute trigger bars
- `backend/app/providers/polygon_adapter.py` - Polygon normalization for 15-second or 1-minute trigger data
- `backend/app/scanner/history.py` - trigger-bar retrieval through the scanner history boundary
- `backend/app/scanner/trigger_policy.py` - preferred and fallback trigger-bar selection
- `backend/app/scanner/trigger_logic.py` - first-break trigger evaluation
- `backend/app/scanner/invalidation.py` - deterministic invalidation decisions
- `backend/tests/scanner_strategy/test_trigger_logic.py` - trigger-bar and first-break coverage
- `backend/tests/scanner_strategy/test_invalidations.py` - invalidation coverage for contradiction, context loss, halts, and dead moves

## Decisions & Deviations

- Bullish candle confirmation is preserved as a recorded quality signal, but the trigger does not require a specific candle pattern in v1.
- Invalidation is evaluated after `setup_valid` so the system can distinguish between a setup that never qualified and one that later degraded.
- No deviations from the plan scope were needed.

## Next Phase Readiness

- Plan `03-03` can score and tag rows using explicit trigger and invalidation outputs instead of inferential heuristics.
- Phase 4 can consume a clear trigger decision and invalidation reason without owning strategy internals.
- No blockers remain for the final Phase 3 ranking and explanation layer.
