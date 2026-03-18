---
phase: 06-telegram-runtime-delivery-and-callback-wiring
plan: 03
subsystem: operator-workflow
tags: [telegram, adjustments, sessions, confirmations, pytest]
requires:
  - phase: 06-02
    provides: live telegram callback route surface and current-state action resolution
provides:
  - guided pre-entry adjustment sessions
  - bounded cancel and timeout handling
  - final confirmation before adjusted approval opens a trade
affects: [phase-06]
tech-stack:
  added: []
  patterns: [bounded chat session, sequential level capture, confirmation-before-open]
key-files:
  created:
    - backend/app/alerts/adjustment_sessions.py
    - backend/app/api/telegram_adjustments.py
    - backend/tests/operator_workflow/test_adjustment_sessions.py
  modified:
    - backend/app/alerts/action_execution.py
    - backend/app/alerts/approval_workflow.py
    - backend/app/alerts/telegram_renderer.py
    - backend/app/api/telegram_callbacks.py
    - backend/tests/operator_workflow/test_telegram_callback_routes.py
key-decisions:
  - "Kept guided adjustments as a narrow pre-entry session flow over the existing callback route instead of introducing a general Telegram bot framework."
  - "Allowed one-sided edits by letting the operator reply with 'keep' for either stop or target while preserving the other proposed value."
  - "Required a final text confirmation before adjusted approval opens the paper trade."
patterns-established:
  - "Session progression: adjust callback -> stop prompt -> target prompt -> confirm/cancel"
  - "Operator feedback stays specific for cancel, expiry, stale alert state, and invalid message input"
requirements-completed: [FLOW-03, FLOW-02]
duration: 1 task batch
completed: 2026-03-18
---

# Phase 6: Telegram Runtime Delivery and Callback Wiring Summary

**Guided Telegram entry adjustments now run as bounded chat sessions with one-sided edits, timeout/cancel handling, and final confirmation before adjusted approval**

## Performance

- **Completed:** 2026-03-18T22:50:00Z
- **Tasks:** 2
- **Primary verification:** `uv run pytest backend/tests/operator_workflow/test_adjustment_sessions.py backend/tests/operator_workflow/test_telegram_callback_routes.py -q`

## Accomplishments

- Added a dedicated adjustment-session state store for actionable pre-entry alerts with sequential stop/target capture.
- Introduced a Telegram adjustment coordinator that renders stop, target, and confirmation prompts over the existing callback route surface.
- Updated the callback executor to start adjustment sessions from `Adjust` callbacks and to convert confirmed sessions into adjusted approvals through the existing approval workflow.
- Added operator-readable handling for invalid input, cancellation, session expiry, and stale alert confirmation.
- Added unit and route-level tests covering one-sided edits, cancel, expiry, and confirmation-to-trade-open behavior.

## Task Commits

1. **Task 1 + Task 2: Guided adjustment sessions and confirmation flow** - pending commit

## Files Created/Modified

- `backend/app/alerts/adjustment_sessions.py` - bounded adjustment session model and store
- `backend/app/api/telegram_adjustments.py` - session coordinator and Telegram-facing prompt flow
- `backend/app/alerts/action_execution.py` - adjustment callback start and message-driven confirmation path
- `backend/app/alerts/approval_workflow.py` - one-sided adjusted approval support
- `backend/app/alerts/telegram_renderer.py` - prompt and confirmation message rendering helpers
- `backend/app/api/telegram_callbacks.py` - message update handling for in-chat adjustment follow-up
- `backend/tests/operator_workflow/test_adjustment_sessions.py` - session-state coverage
- `backend/tests/operator_workflow/test_telegram_callback_routes.py` - route-level guided adjustment coverage

## Decisions & Deviations

- Touched `backend/app/alerts/action_execution.py` and `backend/app/api/telegram_callbacks.py` in addition to the planned file list because the existing Wave 1 callback surface had no hook for follow-up chat messages; those were the smallest integration points needed to keep the guided flow on the same runtime path.
- Kept the flow text-driven after the initial `Adjust` callback instead of adding extra callback buttons for confirmation to avoid expanding the callback parser and payload format further in Phase 6.

## Issues Encountered

- The initial implementation would have created a package import cycle through `app.api`; this was fixed by moving adjustment-coordinator imports inside executor methods instead of loading them at module import time.

## Next Phase Readiness

- Phase 6 now supports fast default approval and bounded guided adjustment approval over the same Telegram route surface.
- Phase verification can now assess the full pre-entry operator workflow as a runtime behavior rather than as renderer-only or model-only logic.
