---
phase: 04-telegram-workflow-and-paper-broker
plan: 02
subsystem: paper-broker
tags: [python, paper-broker, exits, slippage, pytest]
requires:
  - phase: 04-telegram-workflow-and-paper-broker
    provides: operator decisions and open-trade commands from 04-01
provides:
  - deterministic paper-trade state model
  - configurable slippage with optional partial-fill support
  - automatic protective and responsive exits
  - constrained open-trade override actions
affects: [phase-04, phase-05]
tech-stack:
  added: []
  patterns: [paper-trade-state-model, deterministic-exit-evaluator, narrow-override-surface]
key-files:
  created:
    - backend/app/paper/models.py
    - backend/app/paper/broker.py
    - backend/app/paper/exits.py
    - backend/tests/paper_broker/test_entry_handling.py
    - backend/tests/paper_broker/test_exit_handling.py
  modified: []
key-decisions:
  - "Paper fills apply configurable per-side slippage and keep partial-fill simulation off by default while leaving a clean future extension point."
  - "Open trades use deterministic hard-stop, target, weak-follow-through, and momentum-failure exits."
  - "When a single bar touches both stop and target, the broker uses a conservative stop-first assumption."
patterns-established:
  - "Paper-trade entry consumes approved operator decisions instead of Telegram payload details."
  - "Exit evaluation is separated from Telegram rendering and message transport."
  - "Open-trade operator actions remain limited to close, adjust stop, and adjust target."
requirements-completed: [FLOW-04, FLOW-05, RISK-06, RISK-07]
duration: 18 min
completed: 2026-03-16
---

# Phase 4: Telegram Workflow and Paper Broker Summary

**Paper-trade domain, simulated fills, deterministic exits, and narrow open-trade overrides**

## Accomplishments

- Added explicit `PaperTrade`, `PaperFillPolicy`, and `PaperBroker` contracts for simulated long entries.
- Added configurable fill slippage and optional partial-fill handling without introducing live-venue behavior.
- Added deterministic stop, target, weak-follow-through, and momentum-failure exit evaluation.
- Added broker support for the v1 override set only: close, adjust stop, and adjust target.
- Added focused broker tests that prove entry handling, exit handling, and override behavior remain coherent.

## Key Files

- `backend/app/paper/models.py` - paper-trade state, fill policy, and close/adjust helpers
- `backend/app/paper/broker.py` - approved-entry handling, market-update exits, and override application
- `backend/app/paper/exits.py` - deterministic exit observation, policy, and decision logic
- `backend/tests/paper_broker/test_entry_handling.py` - entry, slippage, and partial-fill-extension coverage
- `backend/tests/paper_broker/test_exit_handling.py` - automatic exit and override coverage

## Verification

- `cd backend && uv run pytest tests/paper_broker/test_entry_handling.py tests/paper_broker/test_exit_handling.py -q`
- Result: 12 passed

## Next Phase Readiness

- Risk gating can now size and allow/reject entries against a stable paper-broker contract.
- Lifecycle recording can attach to broker transitions without rewriting trade-state behavior.
