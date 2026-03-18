---
phase: 06-telegram-runtime-delivery-and-callback-wiring
plan: 04
subsystem: operator-workflow
tags: [telegram, asgi, webhook, runtime, pytest]
requires:
  - phase: 06-02
    provides: callback parsing and runtime execution seams
  - phase: 06-03
    provides: guided adjustment message handling over the callback runtime
provides:
  - served Telegram webhook endpoint at the app boundary
  - ASGI request-path proof for callback execution
  - served-path verification of stale and duplicate callback behavior
affects: [phase-06, phase-06-05]
tech-stack:
  added: []
  patterns: [thin asgi boundary, served webhook wrapper, in-memory request-path verification]
key-files:
  created:
    - backend/tests/operator_workflow/test_telegram_webhook_serving.py
  modified:
    - backend/app/main.py
    - backend/app/api/telegram_routes.py
key-decisions:
  - "Implemented a minimal ASGI callable on BuySignalApp instead of introducing a new HTTP framework dependency just to prove a served boundary."
  - "Kept the webhook path narrow at `/telegram/webhook` and delegated request bodies straight into the existing Telegram runtime handler."
patterns-established:
  - "Served Telegram updates now enter through an ASGI boundary before reaching the existing callback/message executor."
  - "Webhook verification uses an in-memory ASGI request harness so served-path behavior is tested without external dependencies."
requirements-completed: [FLOW-02]
duration: 2 tasks
completed: 2026-03-18
---

# Phase 6: Telegram Runtime Delivery and Callback Wiring Summary

**Telegram callback handling now runs through a real served ASGI webhook boundary instead of only through an in-process helper object**

## Performance

- **Completed:** 2026-03-18T23:14:00Z
- **Tasks:** 2
- **Primary verification:** `uv run pytest backend/tests/operator_workflow/test_telegram_callback_routes.py backend/tests/operator_workflow/test_telegram_webhook_serving.py -q`

## Accomplishments

- Added a minimal ASGI callable to `BuySignalApp` so the app can accept real HTTP webhook traffic.
- Added thin Telegram route handling for `POST /telegram/webhook` with JSON validation and narrow scope.
- Verified that valid, stale, and duplicate Telegram callbacks behave correctly when posted through the served app boundary instead of direct method calls.
- Kept the webhook surface Phase-6-scoped and left broader dashboard serving concerns untouched.

## Task Commits

1. **Task 1: Add a genuinely served Telegram webhook endpoint at the app boundary** - `15ea897` (feat)
2. **Task 2: Route served Telegram requests through the existing callback runtime and preserve stale/idempotent behavior** - completed with no additional code changes beyond Task 1; verified by served-path tests

## Files Created/Modified

- `backend/app/main.py` - app object is now a minimal ASGI callable for Telegram webhook traffic
- `backend/app/api/telegram_routes.py` - thin HTTP request handling for the Telegram webhook path
- `backend/tests/operator_workflow/test_telegram_webhook_serving.py` - served-path verification for ignored, accepted, stale, and duplicate callback behavior

## Decisions & Deviations

- Did not modify `backend/app/api/telegram_callbacks.py` because the existing callback handler already satisfied the runtime semantics once exercised through the new served boundary.
- Kept the served app surface limited to Telegram webhook traffic rather than starting general dashboard route serving in this gap-closure plan.

## Issues Encountered

None.

## Next Phase Readiness

- Plan `06-05` can now verify open-trade stop/target overrides through a genuinely served callback boundary instead of the prior in-process facade.
- The Phase 6 verifier can now assess `FLOW-02` against a real app-level webhook path.
