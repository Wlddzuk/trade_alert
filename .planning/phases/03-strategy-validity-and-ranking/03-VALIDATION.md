---
phase: 03
slug: strategy-validity-and-ranking
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-15
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/scanner_strategy -q` |
| **Full suite command** | `cd backend && uv run pytest -q` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/scanner_strategy -q`
- **After every plan wave:** Run `cd backend && uv run pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SCAN-05, SIG-01 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_setup_validity.py -q` | ⬜ planned | ⬜ pending |
| 03-01-02 | 01 | 1 | SCAN-05, SIG-01, SIG-02 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_setup_validity.py -q` | ⬜ planned | ⬜ pending |
| 03-02-01 | 02 | 2 | SIG-03 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_trigger_logic.py -q` | ⬜ planned | ⬜ pending |
| 03-02-02 | 02 | 2 | SIG-03, SIG-04 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_trigger_logic.py tests/scanner_strategy/test_invalidations.py -q` | ⬜ planned | ⬜ pending |
| 03-03-01 | 03 | 3 | SCAN-06, SCAN-05 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_ranking.py -q` | ⬜ planned | ⬜ pending |
| 03-03-02 | 03 | 3 | SCAN-06, SIG-04 | unit/service | `cd backend && uv run pytest tests/scanner_strategy/test_ranking.py tests/scanner_strategy/test_stage_tags.py -q` | ⬜ planned | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All Phase 3 behaviors should be automatable with deterministic normalized market/news fixtures plus fixed intraday bar sequences. No manual-only verification is expected in this phase.

---

## Validation Sign-Off

- [ ] All tasks have automated verify coverage
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Existing infrastructure covers all phase requirements
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
