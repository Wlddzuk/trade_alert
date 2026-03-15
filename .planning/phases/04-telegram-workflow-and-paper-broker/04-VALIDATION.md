---
phase: 04
slug: telegram-workflow-and-paper-broker
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-15
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/operator_workflow tests/paper_broker -q` |
| **Full suite command** | `cd backend && uv run pytest -q` |
| **Estimated runtime** | ~60-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific verify command
- **After every plan wave:** Run `cd backend && uv run pytest tests/operator_workflow tests/paper_broker -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | FLOW-01 | unit/service | `cd backend && uv run pytest tests/operator_workflow/test_telegram_alerts.py tests/operator_workflow/test_delivery_state.py -q` | ⬜ planned | ⬜ pending |
| 04-01-02 | 01 | 1 | FLOW-02, FLOW-03, FLOW-05 | unit/service | `cd backend && uv run pytest tests/operator_workflow/test_operator_decisions.py tests/operator_workflow/test_open_trade_messages.py -q` | ⬜ planned | ⬜ pending |
| 04-02-01 | 02 | 2 | RISK-06, RISK-07 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_entry_handling.py -q` | ⬜ planned | ⬜ pending |
| 04-02-02 | 02 | 2 | FLOW-04, FLOW-05 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_exit_handling.py -q` | ⬜ planned | ⬜ pending |
| 04-03-01 | 03 | 3 | SIG-05, RISK-01, RISK-02 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_risk_gates.py -q` | ⬜ planned | ⬜ pending |
| 04-03-02 | 03 | 3 | RISK-03, RISK-04, RISK-05 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_cooldowns.py tests/operator_workflow/test_actionability.py -q` | ⬜ planned | ⬜ pending |
| 04-04-01 | 04 | 4 | P4-LIFECYCLE, FLOW-02, FLOW-03, FLOW-04 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_lifecycle_audit.py -q` | ⬜ planned | ⬜ pending |
| 04-04-02 | 04 | 4 | P4-LIFECYCLE, FLOW-05 | unit/service | `cd backend && uv run pytest tests/paper_broker/test_trade_review_log.py -q` | ⬜ planned | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Phase Goal Trace

- **P4-LIFECYCLE**: Persist full paper-trade lifecycle events for downstream review, including surfaced-signal, operator-decision, fill, adjustment, exit, and result history with immutable UTC-safe records.

---

## Manual-Only Verifications

All Phase 4 behaviors should be automatable with deterministic strategy projections, approval decisions, simulated market inputs, and append-only lifecycle fixtures. No manual-only verification is expected in this phase.

---

## Validation Sign-Off

- [ ] All tasks have automated verify coverage
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Existing infrastructure covers all phase requirements
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
