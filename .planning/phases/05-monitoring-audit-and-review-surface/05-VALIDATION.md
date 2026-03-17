---
phase: 05
slug: monitoring-audit-and-review-surface
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-17
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/ops_dashboard tests/audit_review tests/dashboard -q` |
| **Full suite command** | `cd backend && uv run pytest -q` |
| **Estimated runtime** | ~60-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific verify command
- **After every plan wave:** Run `cd backend && uv run pytest tests/ops_dashboard tests/audit_review tests/dashboard -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | OPS-01, OPS-02 | unit/service | `cd backend && uv run pytest tests/ops_dashboard/test_status_overview.py -q` | ⬜ planned | ⬜ pending |
| 05-01-02 | 01 | 1 | OPS-01, OPS-05 | unit/service | `cd backend && uv run pytest tests/ops_dashboard/test_incident_log.py tests/ops_dashboard/test_alert_delivery_health.py -q` | ⬜ planned | ⬜ pending |
| 05-02-01 | 02 | 1 | OPS-03 | unit/service | `cd backend && uv run pytest tests/audit_review/test_trade_review_groups.py -q` | ⬜ planned | ⬜ pending |
| 05-02-02 | 02 | 1 | OPS-04 | unit/service | `cd backend && uv run pytest tests/audit_review/test_pnl_summary.py -q` | ⬜ planned | ⬜ pending |
| 05-03-01 | 03 | 2 | FLOW-06, OPS-01, OPS-02 | integration/route | `cd backend && uv run pytest tests/dashboard/test_dashboard_overview.py -q` | ⬜ planned | ⬜ pending |
| 05-03-02 | 03 | 2 | FLOW-06, OPS-03, OPS-04, OPS-05 | integration/route | `cd backend && uv run pytest tests/dashboard/test_dashboard_review_and_logs.py -q` | ⬜ planned | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All Phase 5 behaviors should be automatable with deterministic trust snapshots, incident fixtures, immutable lifecycle events, and read-only dashboard-rendering assertions. No manual-only verification is expected in this phase.

---

## Validation Sign-Off

- [ ] All tasks have automated verify coverage
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Existing infrastructure covers all phase requirements
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
