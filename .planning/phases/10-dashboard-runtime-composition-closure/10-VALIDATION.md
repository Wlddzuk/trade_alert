---
phase: 10
slug: dashboard-runtime-composition-closure
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py -q` |
| **Full suite command** | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/ops_dashboard/test_status_overview.py tests/ops_dashboard/test_incident_log.py tests/ops_dashboard/test_alert_delivery_health.py tests/paper_broker/test_trade_review_log.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q` |
| **Estimated runtime** | ~25-45 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific dashboard/runtime verification command for the touched composition seam.
- **After every plan wave:** Run `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/ops_dashboard/test_status_overview.py tests/ops_dashboard/test_incident_log.py tests/ops_dashboard/test_alert_delivery_health.py tests/paper_broker/test_trade_review_log.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_runtime_state.py tests/dashboard/test_dashboard_serving.py -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/dashboard/test_dashboard_runtime_state.py` — default runtime composition tests for shared snapshot assembly and stale fallback
- [ ] `backend/tests/dashboard/test_dashboard_auth.py` — default config-backed auth behavior and fail-closed behavior when config is absent
- [ ] `backend/tests/dashboard/test_dashboard_serving.py` — served-boundary dashboard route coverage using default app composition
- [ ] `backend/tests/dashboard/test_dashboard_review_and_logs.py` and `backend/tests/dashboard/test_dashboard_overview.py` — overview/logs/trades/P&L assertions against real composed runtime state

---

## Manual-Only Verifications

All phase behaviors should have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
