---
phase: 01-provider-foundation
slug: provider-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-13
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `cd backend && uv run pytest tests/provider_foundation -q` |
| **Full suite command** | `cd backend && uv run pytest -q` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/provider_foundation -q`
- **After every plan wave:** Run `cd backend && uv run pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DATA-03, DATA-04 | unit | `cd backend && uv run pytest tests/provider_foundation/test_provider_normalization.py -q` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DATA-03, DATA-04 | unit/integration-lite | `cd backend && uv run pytest tests/provider_foundation/test_provider_normalization.py -q` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | DATA-01, DATA-02 | unit | `cd backend && uv run pytest tests/provider_foundation/test_universe_and_schedule.py -q` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | DATA-01, DATA-02 | unit | `cd backend && uv run pytest tests/provider_foundation/test_universe_and_schedule.py -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | DATA-03, DATA-04 | unit/service | `cd backend && uv run pytest tests/provider_foundation/test_provider_health.py -q` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 3 | DATA-03, DATA-04 | unit/service | `cd backend && uv run pytest tests/provider_foundation/test_provider_health.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/pyproject.toml` — add pytest configuration if absent
- [ ] `backend/tests/provider_foundation/test_provider_normalization.py` — fixtures and assertions for Polygon/Benzinga normalization plus provider update path coverage
- [ ] `backend/tests/provider_foundation/test_universe_and_schedule.py` — runtime-window and universe-filter coverage
- [ ] `backend/tests/provider_foundation/test_provider_health.py` — freshness/degraded/recovery behavior coverage
- [ ] `backend/tests/conftest.py` or equivalent shared fixture module — canned provider payload helpers and time-freezing utilities

---

## Manual-Only Verifications

All Phase 1 behaviors should be automatable. No manual-only verification is expected if planner tasks establish the minimum backend test harness first.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
