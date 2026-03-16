---
phase: 04-telegram-workflow-and-paper-broker
plan: 01
subsystem: alerts
tags: [python, alerts, telegram, operator-workflow, pytest]
requires:
  - phase: 03-strategy-validity-and-ranking
    provides: ranked strategy projections, stage tags, and trigger-ready state
provides:
  - Telegram-ready watch/actionable/blocked/rejected alert models
  - explicit delivery-state handling for watch-to-actionable progression
  - transport-independent operator decisions for pre-entry approval and open-trade controls
affects: [phase-04, phase-05]
tech-stack:
  added: []
  patterns: [telegram-alert-projection, delivery-state-suppression, transport-independent-operator-decisions]
key-files:
  created:
    - backend/app/alerts/__init__.py
    - backend/app/alerts/models.py
    - backend/app/alerts/delivery_state.py
    - backend/app/alerts/approval_workflow.py
    - backend/tests/operator_workflow/test_telegram_alerts.py
    - backend/tests/operator_workflow/test_delivery_state.py
    - backend/tests/operator_workflow/test_operator_decisions.py
    - backend/tests/operator_workflow/test_open_trade_messages.py
  modified:
    - backend/app/alerts/telegram_renderer.py
key-decisions:
  - "A watched setup that becomes trigger-ready now emits a fresh actionable alert rather than mutating the prior watch alert."
  - "Blocked and rejected Telegram follow-ups remain suppressed unless the symbol has already been surfaced to the operator."
  - "Operator actions are represented as transport-independent approval and open-trade command records rather than Telegram-specific business logic."
patterns-established:
  - "Telegram projection consumes Phase 3 `StrategyProjection` outputs directly."
  - "Pre-entry and open-trade message rendering stay separate from operator-decision records."
  - "Material-event trade messaging uses explicit open/adjusted/closed message types with narrow control buttons."
requirements-completed: [FLOW-01, FLOW-02, FLOW-03, FLOW-05]
duration: 20 min
completed: 2026-03-16
---

# Phase 4: Telegram Workflow and Paper Broker Summary

**Telegram-led alert projection, delivery-state handling, approval decisions, and material-event open-trade controls**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-16T00:02:01Z
- **Completed:** 2026-03-16T00:22:24Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added alert-domain models for pre-entry watch/actionable/blocked/rejected states plus open-trade snapshots and trade-opened/adjusted/closed message events.
- Added Telegram delivery-state handling so watched setups emit a fresh actionable alert when they become trigger-ready and blocked/rejected updates stay limited to already-surfaced symbols.
- Added transport-independent operator-decision records for default approval, adjusted approval, rejection, and open-trade close/adjust-stop/adjust-target actions.
- Added Telegram rendering for actionable pre-entry messages and material-event open-trade messages with the narrow control surface chosen for v1.

## Task Commits

1. **Task 1: Implement Telegram alert projection, delivery-state handling, and rendering for watch/actionable/blocked/rejected progression** - `50d8464` (feat)
2. **Task 2: Implement Telegram operator inputs for pre-entry approval and open-trade material-event controls** - `4c7c0ce` (feat)

## Files Created/Modified

- `backend/app/alerts/models.py` - alert-domain contracts for pre-entry alerts, trade proposals, open-trade snapshots, and material-event message data
- `backend/app/alerts/delivery_state.py` - Telegram delivery-state tracking and suppression rules
- `backend/app/alerts/telegram_renderer.py` - rendering for pre-entry and open-trade Telegram messages plus control buttons
- `backend/app/alerts/approval_workflow.py` - transport-independent approval, rejection, and open-trade command records
- `backend/tests/operator_workflow/test_telegram_alerts.py` - alert projection and pre-entry rendering coverage
- `backend/tests/operator_workflow/test_delivery_state.py` - watch-to-actionable progression and surfaced-symbol suppression coverage
- `backend/tests/operator_workflow/test_operator_decisions.py` - approval and open-trade command coverage
- `backend/tests/operator_workflow/test_open_trade_messages.py` - trade-opened/adjusted/closed Telegram message coverage

## Decisions & Deviations

- The interrupted executor had already landed the Task 1 commit on the current branch, so Wave 1 execution resumed locally from that committed state rather than redoing the same slice.
- Actionable pre-entry alerts now expose explicit `Approve`, `Adjust`, and `Reject` controls, while open-trade messages expose only `Close`, `Adjust Stop`, and `Adjust Target`.
- No scope deviations were needed once the fresh actionable-alert rule and open-trade Telegram controls were made explicit.

## Next Phase Readiness

- Plan `04-02` can open simulated paper trades directly from the new operator-decision records instead of parsing Telegram message state.
- Plan `04-03` can later gate alert actionability and entry eligibility without changing the Phase 4 Telegram contract chosen here.
- No blockers remain for the paper-broker implementation wave.
