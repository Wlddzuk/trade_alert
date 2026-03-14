---
phase: 02
slug: scanner-metrics-and-candidate-feed
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-14
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/scanner_feed -q` |
| **Full suite command** | `cd backend && uv run pytest -q` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/scanner_feed -q`
- **After every plan wave:** Run `cd backend && uv run pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SCAN-02, SCAN-03 | unit/service | `cd backend && uv run pytest tests/scanner_feed/test_metric_calculations.py -q` | ⬜ planned | ⬜ pending |
| 02-01-02 | 01 | 1 | SCAN-02, SCAN-03, SCAN-04 | unit/service | `cd backend && uv run pytest tests/scanner_feed/test_metric_calculations.py -q` | ⬜ planned | ⬜ pending |
| 02-02-01 | 02 | 2 | DATA-05, SCAN-01 | unit | `cd backend && uv run pytest tests/scanner_feed/test_candidate_rows.py -q` | ⬜ planned | ⬜ pending |
| 02-02-02 | 02 | 2 | DATA-05, SCAN-01, SCAN-04 | unit/service | `cd backend && uv run pytest tests/scanner_feed/test_candidate_rows.py -q` | ⬜ planned | ⬜ pending |
| 02-03-01 | 03 | 3 | SCAN-01 | unit/stateful-service | `cd backend && uv run pytest tests/scanner_feed/test_candidate_feed.py -q` | ⬜ planned | ⬜ pending |
| 02-03-02 | 03 | 3 | DATA-05, SCAN-01 | unit/stateful-service | `cd backend && uv run pytest tests/scanner_feed/test_candidate_feed.py -q` | ⬜ planned | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All Phase 2 behaviors should be automatable with deterministic market/news fixtures and feed-state tests. No manual-only verification is expected in this phase.

---

## Validation Sign-Off

- [ ] All tasks have automated verify coverage
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Existing infrastructure covers all phase requirements
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
