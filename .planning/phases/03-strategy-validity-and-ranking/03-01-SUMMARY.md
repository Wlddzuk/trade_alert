---
phase: 03-strategy-validity-and-ranking
plan: 01
subsystem: scanner
tags: [python, scanner, strategy, validity, pytest]
requires:
  - phase: 02-scanner-metrics-and-candidate-feed
    provides: candidate rows, linked-news semantics, and scanner metric context
provides:
  - configurable phase-three strategy defaults
  - first-headline catalyst freshness evaluation
  - fail-closed setup-valid evaluation over catalyst, move, volume, trend, and pullback context
affects: [phase-03, phase-04, phase-05]
tech-stack:
  added: []
  patterns: [configurable-strategy-defaults, first-headline-freshness, fail-closed-validity]
key-files:
  created:
    - backend/app/scanner/strategy_defaults.py
    - backend/app/scanner/strategy_models.py
    - backend/app/scanner/context_features.py
    - backend/app/scanner/setup_validity.py
    - backend/tests/scanner_strategy/test_setup_validity.py
  modified:
    - backend/app/scanner/news_linking.py
key-decisions:
  - "Strategy defaults stay explicit and configurable rather than being hidden inside scanner math or provider code."
  - "Catalyst freshness is anchored to the first headline in the linked catalyst cluster, not the latest update headline."
  - "Setup validity fails closed in a deterministic order so operators always get one primary invalid reason."
patterns-established:
  - "Context features are derived separately from raw candidate rows before validity rules are evaluated."
  - "Validity evaluation consumes normalized scanner context without mutating candidate-row identity."
  - "Primary invalid reason is part of the validity contract rather than ad hoc UI copy."
requirements-completed: [SCAN-05, SIG-01, SIG-02]
duration: 3 min
completed: 2026-03-15
---

# Phase 3: Strategy Validity and Ranking Summary

**Configurable setup-valid defaults and fail-closed validity evaluation for catalyst freshness, move strength, RVOL, trend, and pullback structure**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-15T07:20:58Z
- **Completed:** 2026-03-15T07:23:57Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added explicit Phase 3 strategy defaults for catalyst age, move %, daily RVOL, short-term RVOL, pullback range, and trigger timeframe preferences.
- Added immutable validity models and deterministic context-feature helpers for VWAP, EMA alignment, and pullback retracement context.
- Implemented fail-closed setup-valid evaluation with one primary invalid reason and coverage for stale catalyst, weak move, weak RVOL, broken trend context, and invalid pullback structure.

## Task Commits

1. **Task 1: Implement strategy defaults, validity models, and first-headline freshness support** - `34fa093` (feat)
2. **Task 2: Implement setup-valid evaluation over scanner context** - `bb90f1f` (feat)

## Files Created/Modified

- `backend/app/scanner/strategy_defaults.py` - configurable Phase 3 strategy defaults
- `backend/app/scanner/strategy_models.py` - setup-valid contract and invalid-reason enum
- `backend/app/scanner/news_linking.py` - first-headline catalyst-age helpers
- `backend/app/scanner/context_features.py` - VWAP, EMA, and pullback context derivation
- `backend/app/scanner/setup_validity.py` - ordered fail-closed validity evaluation
- `backend/tests/scanner_strategy/test_setup_validity.py` - coverage for defaults, freshness, context features, and validity checks

## Decisions & Deviations

- Freshness uses the first headline in the active catalyst cluster so late follow-up headlines do not reset setup age artificially.
- Pullback volume quality remains a soft preference in v1 and is not part of the hard `setup_valid` gate.
- No deviations from the plan scope were needed once the validity ordering and primary-invalid-reason contract were fixed.

## Next Phase Readiness

- Plan `03-02` can evaluate trigger timing and invalidations against a stable `setup_valid` contract instead of re-checking raw scanner fields.
- Plan `03-03` can rank and explain candidates using a single validity output rather than duplicated strategy logic.
- No blockers remain for downstream Phase 3 work.
