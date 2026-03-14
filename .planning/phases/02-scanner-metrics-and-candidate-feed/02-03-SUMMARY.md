---
phase: 02-scanner-metrics-and-candidate-feed
plan: 03
subsystem: scanner
tags: [python, scanner, feed, trust-state, pytest]
requires:
  - phase: 01-provider-foundation
    provides: actionable trust snapshots and runtime session semantics
  - phase: 02-scanner-metrics-and-candidate-feed
    provides: symbol-centric candidate rows with latest-headline semantics
provides:
  - symbol-keyed live candidate-feed state with inactivity expiry
  - provisional feed ordering by freshest news then % move on day
  - trust-aware update suppression with session carryover coverage
affects: [phase-03, phase-04, phase-05]
tech-stack:
  added: []
  patterns: [symbol-keyed-live-feed, trust-aware-refresh, unified-session-feed]
key-files:
  created:
    - backend/app/scanner/feed_store.py
    - backend/app/scanner/feed_service.py
    - backend/tests/scanner_feed/test_candidate_feed.py
  modified: []
key-decisions:
  - "The live feed stays keyed by symbol and updates rows in place rather than appending feed history as separate visible rows."
  - "Freshest news remains the provisional primary sort key, with % move on day as the tie-break until Phase 3 score/rank exists."
  - "Non-actionable trust blocks new or refreshed candidate surfacing while allowing existing active rows to remain until expiry."
patterns-established:
  - "Feed lifecycle and ordering are isolated behind a dedicated store/service pair."
  - "Trust gating happens at feed refresh time rather than being spread across metric and row-assembly layers."
  - "Premarket and regular-session candidates share one unified feed as long as the row remains active."
requirements-completed: [DATA-05, SCAN-01]
duration: 3 min
completed: 2026-03-14
---

# Phase 2: Scanner Metrics and Candidate Feed Summary

**Live symbol-keyed candidate feed with inactivity expiry, freshest-news ordering, and trust-aware update suppression**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T21:56:45Z
- **Completed:** 2026-03-14T21:59:53Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a candidate-feed store that keeps one current row per symbol, refreshes rows in place, and expires stale rows after a configurable inactivity window.
- Added a feed service that applies the provisional Phase 2 ordering, respects the actionable trust gate from Phase 1, and keeps the feed unified across the 09:30 ET transition.
- Added focused feed-state coverage for ordering, in-place updates, expiry, trust-aware suppression, and session carryover.

## Task Commits

1. **Task 1 and Task 2: Implement candidate-feed lifecycle, ordering, and trust-aware updates** - `3001858` (feat)

## Files Created/Modified

- `backend/app/scanner/feed_store.py` - symbol-keyed live feed state and inactivity expiry rules
- `backend/app/scanner/feed_service.py` - trust-aware refresh flow plus provisional ordering
- `backend/tests/scanner_feed/test_candidate_feed.py` - coverage for feed lifecycle, ordering, trust gating, and regular-open carryover

## Decisions & Deviations

- Kept the feed unified across premarket and regular session because the operator workflow is continuous and should not split active movers into separate lists at the open.
- Suppressed new or refreshed feed rows whenever trust is non-actionable so stale provider conditions cannot silently refresh scanner output.
- No deviations from the plan scope were needed once the feed lifecycle and trust boundary were fixed.

## Next Phase Readiness

- Phase 3 can consume a stable live candidate feed instead of rebuilding row ordering, lifecycle, or trust handling.
- The scanner foundation now exposes the exact inputs Phase 3 needs for configurable validity rules, trigger logic, and score/rank modeling.
- No blockers remain for Phase 2 completion.
