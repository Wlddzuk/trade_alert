---
phase: 04-telegram-workflow-and-paper-broker
plan: 03
subsystem: risk
tags: [python, risk, sizing, cooldowns, actionability, pytest]
requires:
  - phase: 04-telegram-workflow-and-paper-broker
    provides: Telegram operator workflow plus paper-broker entry surface
provides:
  - reusable fixed-risk sizing
  - trade-quality rejection rules
  - session-level protections and cooldowns
  - shared actionability and final-entry eligibility
affects: [phase-04, phase-05]
tech-stack:
  added: []
  patterns: [shared-entry-eligibility, fixed-risk-sizing, blocked-trigger-ready-surface]
key-files:
  created:
    - backend/app/risk/models.py
    - backend/app/risk/sizing.py
    - backend/app/risk/trade_gates.py
    - backend/app/risk/session_guards.py
    - backend/tests/paper_broker/test_risk_gates.py
    - backend/tests/paper_broker/test_cooldowns.py
    - backend/tests/operator_workflow/test_actionability.py
  modified:
    - backend/app/alerts/approval_workflow.py
    - backend/app/paper/broker.py
key-decisions:
  - "Trade-quality failures such as wide spread, poor liquidity, or unusable stop distance reject a setup outright."
  - "Session-level protections such as cooldowns, cutoff time, max daily loss, and max-open-position limits block trigger-ready setups without dropping them."
  - "The same eligibility contract drives both Telegram actionability and the final paper-trade open."
patterns-established:
  - "Fixed-risk sizing uses the approved proposal values, including adjusted stops."
  - "Trigger-ready blocked setups remain visible as `BLOCKED` rather than becoming approval-capable."
  - "Final entry checks reuse the exact same eligibility decision used for alert actionability."
requirements-completed: [SIG-05, RISK-01, RISK-02, RISK-03, RISK-04, RISK-05]
duration: 17 min
completed: 2026-03-16
---

# Phase 4: Telegram Workflow and Paper Broker Summary

**Fixed-risk sizing, shared entry eligibility, and session-level protections**

## Accomplishments

- Added a small `risk/` domain for defaults, position sizing, trade-quality snapshots, session state, and explicit allow/block/reject decisions.
- Added fixed-risk sizing based on approved entry and stop values rather than raw scanner defaults.
- Added trade-quality rejection for missing stop, wide spread, thin liquidity, and oversized stop distance under the fixed-risk model.
- Added session guards for max daily loss, max open positions, entry cutoff, and loss-based cooldowns.
- Added a shared eligibility combiner so Telegram actionability and final paper-trade open stay aligned.

## Key Files

- `backend/app/risk/models.py` - risk defaults, gate decisions, session-state models, and shared entry eligibility
- `backend/app/risk/sizing.py` - fixed-risk quantity calculation
- `backend/app/risk/trade_gates.py` - trade-quality gating for spread, liquidity, stop presence, and size viability
- `backend/app/risk/session_guards.py` - cutoff, cooldown, daily-loss, and max-position protection
- `backend/app/alerts/approval_workflow.py` - eligibility composition and trigger-ready alert projection
- `backend/app/paper/broker.py` - final entry enforcement against actionable eligibility

## Verification

- `cd backend && uv run pytest tests/paper_broker/test_risk_gates.py tests/paper_broker/test_cooldowns.py tests/operator_workflow/test_actionability.py -q`
- Result: 15 passed

## Next Phase Readiness

- Lifecycle logging can now capture not just trade events but also the allow/block/reject decisions that shaped them.
- The Phase 5 dashboard can surface blocked status and session protections from explicit contracts instead of inferred state.
