---
phase: 06-telegram-runtime-delivery-and-callback-wiring
plan: 05
subsystem: operator-workflow
tags: [telegram, runtime, trade-overrides, served-webhook, pytest]
requires:
  - phase: 06-04
    provides: served Telegram webhook boundary
provides:
  - live stop/target override execution over the Telegram runtime
  - bounded follow-up override input flow per operator
  - served-path verification for open-trade override behavior
affects: [phase-06]
tech-stack:
  added: []
  patterns: [pending trade override session, broker-backed level update, current-state-aware responses]
key-files:
  created:
    - backend/tests/operator_workflow/test_open_trade_overrides.py
  modified:
    - backend/app/alerts/action_execution.py
    - backend/app/alerts/action_resolution.py
    - backend/tests/operator_workflow/test_telegram_callback_routes.py
key-decisions:
  - "Kept trade overrides on the existing callback plus follow-up message path instead of inventing a second control surface or expanding callback payload size."
  - "Stored one pending trade-override session per operator in the existing Telegram runtime registry so overrides stay narrow and current-state-aware."
patterns-established:
  - "Trade override flow: callback starts stop/target override -> next operator message supplies level -> broker command applies update"
  - "Override responses reuse current trade-state text so successful, stale, and duplicate behaviors stay explicit"
requirements-completed: [FLOW-05]
duration: 2 tasks
completed: 2026-03-18
---

# Phase 6: Telegram Runtime Delivery and Callback Wiring Summary

**Open-trade `Adjust Stop` and `Adjust Target` actions now execute through the live Telegram runtime and return current-state-aware responses**

## Performance

- **Completed:** 2026-03-18T23:27:00Z
- **Tasks:** 2
- **Primary verification:** `uv run pytest backend/tests/operator_workflow/test_telegram_callback_routes.py backend/tests/operator_workflow/test_open_trade_overrides.py -q`

## Accomplishments

- Added pending trade-override session handling to the Telegram runtime registry so stop and target edits can collect the new level from the next operator message.
- Wired `trade:st:*` and `trade:tg:*` callbacks into `adjust_trade_stop` and `adjust_trade_target` broker-backed commands rather than leaving them at a generic follow-up placeholder.
- Updated runtime responses so successful stop/target changes report the fresh trade state immediately, while stale and duplicate callback behavior remains explicit.
- Added focused tests for stop/target overrides through both the callback route facade and the served webhook boundary.

## Task Commits

1. **Task 1 + Task 2: Open-trade stop/target override execution and served-path verification** - pending commit

## Files Created/Modified

- `backend/app/alerts/action_execution.py` - runtime stop/target override handling over broker commands
- `backend/app/alerts/action_resolution.py` - pending trade override session tracking
- `backend/tests/operator_workflow/test_telegram_callback_routes.py` - direct runtime coverage for stop/target overrides and stale trade behavior
- `backend/tests/operator_workflow/test_open_trade_overrides.py` - served-path coverage for override success, invalid input, and duplicate callback behavior

## Decisions & Deviations

- Did not modify `backend/app/paper/broker.py` because the existing broker command seam already supported stop and target adjustments once the runtime executor actually dispatched them.
- Kept open-trade overrides to a narrow callback-plus-message flow so the fix closes FLOW-05 without introducing a broader Telegram command framework.

## Issues Encountered

None.

## Next Phase Readiness

- Phase verification can now reassess FLOW-05 against a live served callback path rather than a parser-only placeholder.
- The runtime now supports all Phase 4 operator override buttons end to end.
