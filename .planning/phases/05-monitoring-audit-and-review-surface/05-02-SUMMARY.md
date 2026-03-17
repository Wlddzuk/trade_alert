---
phase: 05-monitoring-audit-and-review-surface
plan: 02
subsystem: audit
tags: [audit, trade-review, pnl, lifecycle, read-models]
requires:
  - phase: 04-telegram-workflow-and-paper-broker
    provides: immutable lifecycle events and trade review seams
provides:
  - grouped completed-trade review feed by trading day
  - summary-first completed trade records with raw-event drill-down
  - today-first realized paper P&L summaries with day-by-day history
affects: [phase-05-dashboard, trade-review, paper-pnl]
tech-stack:
  added: []
  patterns: [immutable lifecycle derivation, day-grouped review feeds, realized-first pnl summaries]
key-files:
  created: [backend/tests/audit_review/__init__.py]
  modified: [backend/app/audit/review_models.py, backend/app/audit/review_service.py, backend/app/audit/pnl_summary.py, backend/tests/audit_review/test_trade_review_groups.py, backend/tests/audit_review/test_pnl_summary.py]
key-decisions:
  - "Completed-trade review stays derived from immutable lifecycle events instead of mutable broker state."
  - "Paper P&L remains realized-first and today-first, with day-by-day history instead of chart-first analytics."
patterns-established:
  - "Review feed pattern: newest closed trades first within each trading day, with raw lifecycle events preserved as secondary detail."
  - "P&L summary pattern: compute per-day realized rows, then derive today and cumulative aggregates from the same review feed."
requirements-completed: [OPS-03, OPS-04]
duration: 6min
completed: 2026-03-17
---

# Phase 5 Plan 02: Audit Review and P&L Summary

**Day-grouped completed-trade review feed and realized-first paper P&L summaries over immutable lifecycle events**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-17T07:10:00Z
- **Completed:** 2026-03-17T07:16:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added completed-trade review models grouped by trading day with newest-first ordering.
- Preserved raw lifecycle events as secondary drill-down detail behind the human-readable review feed.
- Added today-first, realized-first P&L summaries with cumulative context and day-by-day history.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement day-grouped trade-review read models with summary-first drill-down** - `0cd3fc3` (`feat`)
2. **Task 2: Implement realized-first paper-P&L summaries and day-by-day history** - `5dc9ba1` (`feat`)

## Files Created/Modified
- `backend/app/audit/review_models.py` - Dataclasses for completed-trade review rows and day groups.
- `backend/app/audit/review_service.py` - Immutable lifecycle to review-feed composition.
- `backend/app/audit/pnl_summary.py` - Today-first realized P&L summary service and daily history rows.
- `backend/tests/audit_review/test_trade_review_groups.py` - Coverage for newest-first grouping and raw-event retention.
- `backend/tests/audit_review/test_pnl_summary.py` - Coverage for today-first P&L and win-rate aggregation.
- `backend/tests/audit_review/__init__.py` - Ensures the audit-review test package imports cleanly.

## Decisions Made
- Review grouping is anchored to the trade close day in UTC-safe time so the operator sees completed outcomes by trading day.
- P&L summaries derive from the review feed instead of maintaining a second aggregation source.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `tests/audit_review/` needed an `__init__.py` package marker so the new audit-review test modules could import consistently under pytest.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 now has immutable review and paper-P&L read models ready for dashboard composition.
- Plan 05-03 can render review and P&L sections without reaching into broker state directly.

## Self-Check: PASSED

- Found: `.planning/phases/05-monitoring-audit-and-review-surface/05-02-SUMMARY.md`
- Found commit: `0cd3fc3`
- Found commit: `5dc9ba1`
- Verified: `cd backend && uv run pytest tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q`

---
*Phase: 05-monitoring-audit-and-review-surface*
*Completed: 2026-03-17*
