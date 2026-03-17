---
phase: 05-monitoring-audit-and-review-surface
plan: 02
subsystem: audit
tags: [audit-review, lifecycle-log, pnl, paper-trades, review-feed]
requires:
  - phase: 04-telegram-workflow-and-paper-broker
    provides: immutable paper-trade lifecycle events and trade review seams
provides:
  - day-grouped completed-trade review feed
  - raw-event drill-down attached to human-readable trade reviews
  - today-first realized paper P&L summary with daily history
affects: [dashboard, trade-review, phase-05-03]
tech-stack:
  added: []
  patterns: [immutable review composition, review-driven pnl summaries]
key-files:
  created: [backend/app/audit/review_models.py, backend/app/audit/review_service.py, backend/app/audit/pnl_summary.py, backend/tests/audit_review/test_trade_review_groups.py, backend/tests/audit_review/test_pnl_summary.py]
  modified: []
key-decisions:
  - "Completed-trade review stays derived from immutable lifecycle events rather than mutable broker snapshots."
  - "P&L summaries derive from the review feed so review and performance stay on a single source of truth."
patterns-established:
  - "Audit review pattern: summary-first trade records with raw lifecycle events attached as secondary drill-down."
  - "P&L pattern: today-first realized summary plus simple daily history, not chart-first analytics."
requirements-completed: [OPS-03, OPS-04]
duration: 18min
completed: 2026-03-17
---

# Phase 5 Plan 02: Audit Review and P&L Summary

**Day-grouped immutable trade review feed with today-first realized paper-P&L summaries derived from the same lifecycle history**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-17T07:15:00Z
- **Completed:** 2026-03-17T07:33:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added a completed-trade review feed grouped by trading day with newest trades first inside each day.
- Kept raw lifecycle events attached to each review record as secondary drill-down detail.
- Added a today-first realized P&L summary with cumulative context and day-by-day trade-count and win-rate history.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement day-grouped trade-review read models with summary-first drill-down** - `0cd3fc3` (feat)
2. **Task 2: Implement realized-first paper-P&L summaries and day-by-day history** - `5dc9ba1` (feat)

## Files Created/Modified
- `backend/app/audit/review_models.py` - Completed-trade review and day-grouping read models.
- `backend/app/audit/review_service.py` - Lifecycle-to-review composition service.
- `backend/app/audit/pnl_summary.py` - Today-first realized P&L summary service and daily history models.
- `backend/tests/audit_review/test_trade_review_groups.py` - Coverage for day grouping, ordering, and raw-event drill-down.
- `backend/tests/audit_review/test_pnl_summary.py` - Coverage for today-first realized results, win rate, and history.

## Decisions Made
- Trade review groups by trade close day so operators review completed work on the day it resolved.
- Raw lifecycle events remain attached to review records but never replace the human-readable summary view.
- P&L summaries are derived from the same review feed instead of a parallel calculation path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 dashboard composition can now consume stable ops, review, and P&L read models from backend services.
- No blockers remain for the read-only dashboard route layer.

## Self-Check: PASSED

- Verified summary file exists.
- Verified task commits `0cd3fc3` and `5dc9ba1` exist in git history.
