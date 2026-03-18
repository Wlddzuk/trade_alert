---
phase: 06-telegram-runtime-delivery-and-callback-wiring
plan: 02
subsystem: operator-workflow
tags: [python, telegram, callbacks, paper-broker, pytest]
requires: []
provides:
  - minimal telegram callback route surface
  - callback parsing and current-state resolution
  - idempotent duplicate handling with stale-state feedback
affects: [phase-06]
tech-stack:
  added: []
  patterns: [thin-route-facade, injectable-callback-executor, current-state-registry]
key-files:
  created:
    - backend/app/api/telegram_routes.py
    - backend/app/api/telegram_callbacks.py
    - backend/app/alerts/action_resolution.py
    - backend/app/alerts/action_execution.py
    - backend/tests/operator_workflow/test_telegram_callback_routes.py
  modified:
    - backend/app/main.py
    - backend/app/api/__init__.py
key-decisions:
  - "Kept the live API surface framework-free and route-like instead of introducing FastAPI/Starlette before Phase 7."
  - "Resolved callback validity from current alert and trade state by ID, not chat history, so stale and superseded actions fail clearly."
  - "Handled duplicate callback deliveries idempotently by memoizing callback-query responses."
patterns-established:
  - "Telegram callback payloads are parsed once, then routed through an injectable executor over existing approval and broker primitives."
  - "Runtime state is tracked through a dedicated registry that owns latest-alert and latest-trade semantics."
requirements-completed: [FLOW-02, FLOW-05]
duration: 1 task batch
completed: 2026-03-18
---

# Phase 6: Telegram Runtime Delivery and Callback Wiring Summary

**Minimal Telegram callback route surface with stale-safe action resolution and broker-backed command execution**

## Performance

- **Completed:** 2026-03-18T22:33:12Z
- **Tasks:** 2
- **Primary verification:** `uv run pytest tests/operator_workflow/test_telegram_callback_routes.py -q`

## Accomplishments

- Added a thin Telegram update route facade to the app boundary without introducing a broader web framework or Phase 7 dashboard-serving scope.
- Implemented callback parsing and current-state resolution for entry and open-trade actions using live alert/trade IDs rather than chat-local history.
- Wired valid approve/reject/close callbacks into the existing approval workflow and paper broker, with stale action rejection and duplicate callback idempotency.
- Added route-level tests covering approve, stale, duplicate, close, and adjustment follow-up behavior.

## Task Commits

1. **Task 1 + Task 2: Telegram callback route and action-dispatch path** - pending orchestrator commit

## Files Created/Modified

- `backend/app/main.py` - app composition now exposes a Telegram route surface alongside dashboard helpers
- `backend/app/api/__init__.py` - exports the Telegram route and callback helpers
- `backend/app/api/telegram_routes.py` - thin Telegram update entrypoint
- `backend/app/api/telegram_callbacks.py` - callback update handler and route response model
- `backend/app/alerts/action_resolution.py` - callback parsing plus current alert/trade resolution registry
- `backend/app/alerts/action_execution.py` - executor that maps valid callbacks into approval and broker primitives
- `backend/tests/operator_workflow/test_telegram_callback_routes.py` - route-level coverage for callback execution semantics

## Decisions & Deviations

- Kept the route surface framework-free because `backend/pyproject.toml` has no HTTP stack yet and this plan only needed the minimal runtime control seam.
- Returned `needs_input` for adjustment callbacks so Wave 2 can layer the guided adjustment session flow cleanly without overloading Plan 06-02.
- Did not update shared planning artifacts like `STATE.md` or `ROADMAP.md` from this parallel worker to avoid write collisions; the phase orchestrator can aggregate those updates safely.

## Next Phase Readiness

- Plan `06-03` can build guided stop/target adjustment sessions on top of the new callback route and executor seams.
- The app now has a narrow Telegram runtime control surface ready for extension without dragging in the dashboard-serving phase.
