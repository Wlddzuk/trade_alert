---
phase: 02-scanner-metrics-and-candidate-feed
plan: 01
subsystem: scanner
tags: [python, scanner, metrics, polygon, pytest]
requires:
  - phase: 01-provider-foundation
    provides: provider contracts, normalized market snapshots, and trusted runtime boundaries
provides:
  - normalized daily and 5-minute history inputs behind provider abstractions
  - pure market-metric calculators for move, RVOL, and pullback context
  - deterministic metric-test coverage for Phase 2 scanner fields
affects: [phase-02, phase-03, phase-04]
tech-stack:
  added: []
  patterns: [normalized-history-boundary, pure-metric-functions, ratio-based-rvol]
key-files:
  created:
    - backend/app/scanner/history.py
    - backend/app/scanner/metrics.py
  modified:
    - backend/app/providers/base.py
    - backend/app/providers/models.py
    - backend/app/providers/polygon_adapter.py
    - backend/app/scanner/__init__.py
    - backend/tests/scanner_feed/test_metric_calculations.py
key-decisions:
  - "Kept historical daily and intraday retrieval behind the market-data provider boundary instead of letting scanner code fetch raw Polygon payloads directly."
  - "Implemented scanner metrics as pure functions over normalized models so Phase 2 stays deterministic and Phase 3 can layer strategy rules without rewriting math."
  - "Standardized relative volume outputs as x-multipliers rather than percentage-style values so defaults and operator-facing fields remain consistent."
patterns-established:
  - "Market-history retrieval flows through one scanner history service rather than ad hoc provider calls."
  - "Metric calculation stays strategy-neutral and only exposes scanner context, not setup-valid or invalidation decisions."
  - "Relative-volume baselines are computed from normalized daily bars and same-time-of-day 5-minute bars."
requirements-completed: [SCAN-02, SCAN-03, SCAN-04]
duration: 3 min
completed: 2026-03-14
---

# Phase 2: Scanner Metrics and Candidate Feed Summary

**Normalized daily and intraday history inputs with pure RVOL, move, and pullback metric calculators for the scanner feed**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T19:11:31Z
- **Completed:** 2026-03-14T19:14:01Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Extended the market-data surface so scanner code can retrieve normalized daily and 5-minute baseline history without leaking provider payload details.
- Added deterministic metric calculators for average daily volume, daily RVOL, short-term RVOL, gap %, % change from prior close, and pullback % from high of day.
- Added focused scanner metric tests that verify the baseline math and keep Phase 2 strategy-neutral.

## Task Commits

1. **Task 1: Extend market-data inputs for normalized daily and 5-minute baseline history** - `4f26c48` (feat)
2. **Task 2: Implement pure scanner metric calculators for market move, RVOL, and pullback context** - `f0d17be` (feat)
3. **Verification fix: Correct relative volume scale after test review** - `18e56b6` (fix)

## Files Created/Modified

- `backend/app/providers/base.py` - provider contract extensions for historical daily and intraday bar retrieval
- `backend/app/providers/models.py` - normalized `DailyBar` and `IntradayBar` records
- `backend/app/providers/polygon_adapter.py` - Polygon history normalization for daily and 5-minute baseline inputs
- `backend/app/scanner/history.py` - scanner-facing history retrieval service over provider abstractions
- `backend/app/scanner/metrics.py` - pure calculator functions for move, RVOL, and pullback metrics
- `backend/tests/scanner_feed/test_metric_calculations.py` - deterministic coverage for baseline and metric formulas

## Decisions & Deviations

- Kept the history boundary vendor-agnostic so later provider swaps do not require scanner rewrites.
- Left the metric layer free of `setup_valid`, invalidation, and score/rank logic so Phase 3 remains the first strategy-specific layer.
- A small deviation was needed after verification: daily and short-term RVOL originally returned percentage-style values, and the follow-up fix converted them to x-multipliers to match the configured defaults and row semantics.

## Next Phase Readiness

- Plan `02-02` can assemble candidate rows directly from normalized metrics and latest-headline news context.
- Plan `02-03` can sort and persist live feed rows using deterministic move and freshness fields from this plan.
- No blockers remain for downstream Phase 2 work.
