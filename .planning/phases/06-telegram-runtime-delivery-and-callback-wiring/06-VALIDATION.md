---
phase: 06
slug: telegram-runtime-delivery-and-callback-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` |
| **Full suite command** | `cd backend && uv run pytest` |
| **Estimated runtime** | ~20 seconds quick, ~60 seconds full |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q`
- **After every plan wave:** Run `cd backend && uv run pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | FLOW-01 | unit/integration | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | FLOW-02 | route/integration | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | FLOW-03 | route/integration | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | FLOW-03 | state/integration | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 2 | FLOW-05 | unit/integration | `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/operator_workflow/test_telegram_runtime_delivery.py` — outbound Telegram delivery adapter and retry coverage for FLOW-01
- [ ] `backend/tests/operator_workflow/test_telegram_callback_routes.py` — webhook/callback routing, stale actions, and idempotent responses for FLOW-02 and FLOW-05
- [ ] `backend/tests/operator_workflow/test_adjustment_sessions.py` — guided stop/target adjustment flow, cancel, timeout, and confirmation coverage for FLOW-03
- [ ] `backend/tests/ops_dashboard/test_telegram_runtime_failures.py` — delivery-attempt reporting and incident-log propagation coverage

*Existing infrastructure covers the framework; Wave 0 only needs new test modules and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Telegram message readability and button ergonomics in a real chat | FLOW-01, FLOW-02, FLOW-03, FLOW-05 | Requires real Telegram client behavior and transport credentials | Send one watch alert, one actionable alert, one adjustment flow, and one open-trade override message to a test chat; confirm labels, stale annotations, and operator responses read clearly. |
| Deployment webhook configuration against the target runtime environment | FLOW-02, FLOW-05 | Requires environment-specific callback wiring outside local unit tests | Configure the webhook endpoint in the deployed environment, send a callback from Telegram, and confirm the app receives and processes it end to end. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
