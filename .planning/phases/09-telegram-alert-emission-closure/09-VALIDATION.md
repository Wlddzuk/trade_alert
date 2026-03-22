---
phase: 09
slug: telegram-alert-emission-closure
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/operator_workflow/test_telegram_alert_emission_flow.py tests/operator_workflow/test_telegram_callback_routes.py tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py -q` |
| **Full suite command** | `cd backend && uv run pytest tests/operator_workflow/test_telegram_alert_emission_flow.py tests/operator_workflow/test_telegram_runtime_delivery.py tests/operator_workflow/test_telegram_callback_routes.py tests/operator_workflow/test_adjustment_sessions.py tests/operator_workflow/test_telegram_webhook_serving.py tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py -q` |
| **Estimated runtime** | ~20-40 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific verification command for the touched Telegram runtime path.
- **After every plan wave:** Run `cd backend && uv run pytest tests/operator_workflow/test_telegram_alert_emission_flow.py tests/operator_workflow/test_telegram_runtime_delivery.py tests/operator_workflow/test_telegram_callback_routes.py tests/operator_workflow/test_adjustment_sessions.py tests/operator_workflow/test_telegram_webhook_serving.py tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | FLOW-01 | integration | `cd backend && uv run pytest tests/operator_workflow/test_telegram_alert_emission_flow.py -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | FLOW-01 | integration | `cd backend && uv run pytest tests/operator_workflow/test_telegram_alert_emission_flow.py tests/operator_workflow/test_telegram_runtime_delivery.py -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | FLOW-02 | route/integration | `cd backend && uv run pytest tests/operator_workflow/test_telegram_callback_routes.py tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py -q` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 2 | FLOW-03 | route/integration | `cd backend && uv run pytest tests/operator_workflow/test_adjustment_sessions.py tests/operator_workflow/test_telegram_webhook_serving.py tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/operator_workflow/test_telegram_alert_emission_flow.py` — producer-path emission tests from qualifying setup through successful send and registry registration
- [ ] `backend/tests/operator_workflow/test_telegram_alert_emission_webhook_flow.py` — route and served-boundary approval/adjustment tests that start from emitted alert state
- [ ] shared fixtures or helpers for emitted-alert setup without direct `registry.register_alert(...)` as the primary milestone proof path

---

## Manual-Only Verifications

All phase behaviors should have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
