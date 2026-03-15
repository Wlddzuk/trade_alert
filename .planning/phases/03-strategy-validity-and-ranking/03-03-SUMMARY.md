---
phase: 03-strategy-validity-and-ranking
plan: 03
subsystem: scanner
tags: [python, scanner, ranking, stage-tags, pytest]
requires:
  - phase: 03-strategy-validity-and-ranking
    provides: setup-valid, trigger, and invalidation outputs
provides:
  - quality-first 0-100 scoring for surfaced candidates
  - stage tags and supporting reasons for operator-facing strategy state
  - valid-first strategy ordering without changing the symbol-keyed feed model
affects: [phase-04, phase-05]
tech-stack:
  added: []
  patterns: [quality-first-score, stage-tag-projection, valid-first-ordering]
key-files:
  created:
    - backend/app/scanner/strategy_ranking.py
    - backend/app/scanner/strategy_tags.py
    - backend/app/scanner/strategy_projection.py
    - backend/tests/scanner_strategy/test_ranking.py
    - backend/tests/scanner_strategy/test_stage_tags.py
  modified:
    - backend/app/scanner/feed_service.py
key-decisions:
  - "Ranking remains quality-first and keeps invalid candidates visible for context instead of suppressing them from operator view."
  - "Stage tags are intentionally small and deterministic: building, trigger_ready, and invalidated."
  - "Strategy ordering was added as a separate feed-service helper so Phase 2 feed lifecycle behavior stays intact."
patterns-established:
  - "Projection layers strategy explanation above candidate rows instead of mutating the underlying row contract."
  - "Ordering uses validity bucket first, then score, then freshness and move as tie-breaks."
  - "Supporting reasons are concise machine-readable fragments rather than Telegram-specific formatting."
requirements-completed: [SCAN-06]
duration: 5 min
completed: 2026-03-15
---

# Phase 3: Strategy Validity and Ranking Summary

**Quality-first score, stage-tag projection, and valid-first strategy ordering for operator-facing scanner rows**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T07:28:44Z
- **Completed:** 2026-03-15T07:33:44Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added a deterministic `0-100` quality-first score that rewards validity, catalyst freshness, move strength, RVOL context, pullback quality, and trigger quality.
- Added strategy-stage tags plus supporting reasons so each row can explain whether it is building, trigger-ready, or invalidated.
- Added valid-first strategy ordering as a dedicated service helper so downstream Telegram and paper-trade workflows can consume ranked strategy projections without rewriting the Phase 2 feed lifecycle.

## Task Commits

1. **Task 1: Implement strategy ranking and valid-first ordering** - `1c79c76` (feat)
2. **Task 2: Implement strategy projection and stage tags** - `66d711b` (feat)

## Files Created/Modified

- `backend/app/scanner/strategy_ranking.py` - quality-first scoring for strategy projections
- `backend/app/scanner/strategy_tags.py` - deterministic stage-tag derivation
- `backend/app/scanner/strategy_projection.py` - strategy-aware row projection with score, reasons, and invalid reason
- `backend/app/scanner/feed_service.py` - valid-first strategy-row ordering helper
- `backend/tests/scanner_strategy/test_ranking.py` - score and ordering coverage
- `backend/tests/scanner_strategy/test_stage_tags.py` - stage-tag and supporting-reason coverage

## Decisions & Deviations

- Added a small freshness contribution to the quality score so older but still-valid setups do not outrank fresher catalysts too easily.
- Kept invalid rows visible and sortable below valid ones because the operator still benefits from context on rejected movers.
- There was a minor execution cleanup: ranking tests were decoupled from the projection implementation before the Task 1 commit so the two planned task boundaries could remain clean and independently verifiable.

## Next Phase Readiness

- Phase 4 can alert and route operator decisions from a strategy-aware ranked feed instead of raw scanner rows.
- Phase 5 can present stage tags, reasons, and invalid context in the read-only dashboard without inventing its own explanation model.
- No blockers remain for Phase 3 completion.
