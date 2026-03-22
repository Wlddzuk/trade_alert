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
| **Quick run command** | `cd backend && uv run pytest tests/dashboard/test_dashboard_runtime_state.py tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py -q` |
| **Full suite command** | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/ops_dashboard/test_status_overview.py tests/ops_dashboard/test_incident_log.py tests/ops_dashboard/test_alert_delivery_health.py tests/paper_broker/test_trade_review_log.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q` |
| **Estimated runtime** | smoke ~8-20 seconds; full suite ~25-45 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific smoke command first, then the task-specific primary verification command if the smoke passes.
- **After every plan wave:** Run `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/ops_dashboard/test_status_overview.py tests/ops_dashboard/test_incident_log.py tests/ops_dashboard/test_alert_delivery_health.py tests/paper_broker/test_trade_review_log.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Preferred task feedback latency:** under 20 seconds
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Smoke Command | Primary Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|---------------|---------------------------|-------------|--------|
| 10-01-01 | 01 | 1 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_runtime_state.py -k "default or stale" -q` | `cd backend && uv run pytest tests/dashboard/test_dashboard_runtime_state.py tests/dashboard/test_dashboard_serving.py -q` | ✅ existing | ⬜ pending |
| 10-01-02 | 01 | 1 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py -k "session or fail_closed or login" -q` | `cd backend && uv run pytest tests/dashboard/test_dashboard_auth.py tests/dashboard/test_dashboard_serving.py -q` | ✅ existing | ⬜ pending |
| 10-02-01 | 02 | 2 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_review_and_logs.py -q` | `cd backend && uv run pytest tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q` | ✅ existing | ⬜ pending |
| 10-02-02 | 02 | 2 | FLOW-06 | integration | `cd backend && uv run pytest tests/dashboard/test_dashboard_serving.py -k "dashboard or login or trades or pnl" -q` | `cd backend && uv run pytest tests/dashboard/test_dashboard_serving.py tests/dashboard/test_dashboard_review_and_logs.py tests/dashboard/test_dashboard_overview.py tests/dashboard/test_dashboard_runtime_state.py tests/audit_review/test_trade_review_groups.py tests/audit_review/test_pnl_summary.py -q` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No new Wave 0 plan is required for Phase 10. The referenced test modules already exist and are executable, so Phase 10 uses direct task-level smoke commands plus primary automated commands instead of `❌ W0` placeholders.

- [x] `backend/tests/dashboard/test_dashboard_runtime_state.py` exists for default runtime composition and stale fallback coverage
- [x] `backend/tests/dashboard/test_dashboard_auth.py` exists for config-backed auth and fail-closed behavior
- [x] `backend/tests/dashboard/test_dashboard_serving.py` exists for served-boundary coverage through the default app path
- [x] `backend/tests/dashboard/test_dashboard_review_and_logs.py` and `backend/tests/dashboard/test_dashboard_overview.py` exist for overview/logs/trades/P&L runtime assertions
- [x] `backend/tests/audit_review/test_trade_review_groups.py` and `backend/tests/audit_review/test_pnl_summary.py` exist for lifecycle-backed review and P&L proof

---

## Manual-Only Verifications

All phase behaviors should have automated verification.

---

## Validation Sign-Off

- [x] All tasks have direct automated commands; no Wave 0 placeholders remain
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 45s
- [x] Preferred smoke feedback target is under 20 seconds
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
