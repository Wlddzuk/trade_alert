---
phase: 08
slug: monitoring-verification-recovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 08 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py -q` |
| **Full suite command** | `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py backend/tests/dashboard/test_dashboard_overview.py backend/tests/dashboard/test_dashboard_review_and_logs.py backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_runtime_state.py -q` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run the quick run command if evidence claims or cited commands changed.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | OPS-01, OPS-02, OPS-05 | regression | `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py -q` | ✅ | ⬜ pending |
| 08-01-02 | 01 | 1 | OPS-03, OPS-04 | regression | `uv run pytest backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py -q` | ✅ | ⬜ pending |
| 08-02-01 | 02 | 2 | OPS-01, OPS-02, OPS-03, OPS-04, OPS-05 | regression | `uv run pytest backend/tests/dashboard/test_dashboard_overview.py backend/tests/dashboard/test_dashboard_review_and_logs.py backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_runtime_state.py -q` | ✅ | ⬜ pending |
| 08-02-02 | 02 | 2 | OPS-01, OPS-02, OPS-03, OPS-04, OPS-05 | regression | `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py backend/tests/dashboard/test_dashboard_overview.py backend/tests/dashboard/test_dashboard_review_and_logs.py backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_runtime_state.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Served dashboard sanity check | OPS-01, OPS-03, OPS-04, OPS-05 | Optional confidence check for audit-facing narrative after automated proof is assembled | Load the served dashboard and confirm overview, logs, trades, and P&L remain read-only and consistent with the cited evidence. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
