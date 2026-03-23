---
phase: 07
slug: served-dashboard-runtime-surface
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-18
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `uv run pytest backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_auth.py backend/tests/operator_workflow/test_telegram_webhook_serving.py` |
| **Full suite command** | `uv run pytest backend/tests/dashboard backend/tests/operator_workflow/test_telegram_webhook_serving.py` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_auth.py backend/tests/operator_workflow/test_telegram_webhook_serving.py`
- **After every plan wave:** Run `uv run pytest backend/tests/dashboard backend/tests/operator_workflow/test_telegram_webhook_serving.py`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | FLOW-06 | unit/integration | `uv run pytest backend/tests/dashboard/test_dashboard_serving.py -k route_dispatch` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | FLOW-06 | integration | `uv run pytest backend/tests/dashboard/test_dashboard_serving.py -k root_redirect` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | FLOW-06 | integration | `uv run pytest backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_auth.py -k "dashboard_not_found or fail_closed or session"` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | FLOW-06 | integration | `uv run pytest backend/tests/dashboard/test_dashboard_serving.py -k section_routes` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 2 | FLOW-06 | unit/integration | `uv run pytest backend/tests/dashboard/test_dashboard_runtime_state.py -k "snapshot or stale"` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 2 | FLOW-06 | regression | `uv run pytest backend/tests/dashboard backend/tests/operator_workflow/test_telegram_webhook_serving.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/dashboard/test_dashboard_serving.py` — served app boundary coverage for route dispatch, redirects, HTML responses, and dashboard 404s
- [ ] `backend/tests/dashboard/test_dashboard_auth.py` — lightweight password/session gate coverage
- [ ] `backend/tests/dashboard/test_dashboard_runtime_state.py` — runtime snapshot freshness and stale fallback coverage

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Desktop-first readability with phone-safe quick checks | FLOW-06 | Layout quality and information density are easier to judge visually than through HTML assertions alone | Run the served app, open overview and review routes in a desktop browser and a narrow mobile viewport, and confirm the surface remains read-only, summary-first, and usable for quick checks. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-18
