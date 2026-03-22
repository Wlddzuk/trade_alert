---
phase: 11
slug: audit-traceability-closure
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | shell diff/grep plus artifact review |
| **Config file** | none — planning artifact phase |
| **Quick run command** | `rg -n "08-VERIFICATION|10-02|Last updated|ready_for_verification|percent:" .planning/phases/08-monitoring-verification-recovery .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md .planning/v1.0-MILESTONE-AUDIT.md` |
| **Full suite command** | `test -f .planning/phases/08-monitoring-verification-recovery/08-VERIFICATION.md && rg -n "10-02:|Phase 10|Last updated|ready_for_verification|percent:|31/34|7/8|3/5" .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md .planning/v1.0-MILESTONE-AUDIT.md` |
| **Estimated runtime** | smoke ~2-5 seconds; full suite ~5-10 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific artifact check first.
- **After every plan wave:** Run `test -f .planning/phases/08-monitoring-verification-recovery/08-VERIFICATION.md && rg -n "10-02:|Phase 10|Last updated|ready_for_verification|percent:|31/34|7/8|3/5" .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md .planning/v1.0-MILESTONE-AUDIT.md`
- **Before `$gsd-verify-work`:** Full artifact-consistency check must be green
- **Preferred task feedback latency:** under 10 seconds
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Smoke Command | Primary Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|---------------|---------------------------|-------------|--------|
| 11-01-01 | 01 | 1 | milestone-audit-chain | artifact | `test -f .planning/phases/05-monitoring-audit-and-review-surface/05-VERIFICATION.md && test -f .planning/phases/08-monitoring-verification-recovery/08-01-SUMMARY.md && test -f .planning/phases/08-monitoring-verification-recovery/08-02-SUMMARY.md` | `test -f .planning/phases/08-monitoring-verification-recovery/08-VERIFICATION.md && rg -n "Phase 8|05-VERIFICATION|milestone audit|recovery" .planning/phases/08-monitoring-verification-recovery/08-VERIFICATION.md` | ✅ existing inputs | ⬜ pending |
| 11-02-01 | 02 | 2 | planning-traceability | artifact | `rg -n "10-02|2/2|Complete" .planning/ROADMAP.md && rg -n "Last updated" .planning/REQUIREMENTS.md && rg -n "status:|current_plan:|percent:" .planning/STATE.md` | `rg -n "10-02|2/2|Complete|Last updated|status:|current_plan:|percent:" .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md` | ✅ existing | ⬜ pending |
| 11-02-02 | 02 | 2 | milestone-audit-chain | artifact | `rg -n "FLOW-01|FLOW-02|FLOW-03|FLOW-06|31/34|7/8|3/5" .planning/v1.0-MILESTONE-AUDIT.md` | `rg -n "FLOW-01|FLOW-02|FLOW-03|FLOW-06|08-VERIFICATION|Phase 9|Phase 10" .planning/v1.0-MILESTONE-AUDIT.md` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No Wave 0 plan is required for Phase 11. The work is document-closure only, and all referenced source artifacts already exist on disk.

- [x] `.planning/phases/05-monitoring-audit-and-review-surface/05-VERIFICATION.md` exists
- [x] `.planning/phases/08-monitoring-verification-recovery/08-01-SUMMARY.md` exists
- [x] `.planning/phases/08-monitoring-verification-recovery/08-02-SUMMARY.md` exists
- [x] `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, and `.planning/v1.0-MILESTONE-AUDIT.md` exist

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Audit-facing narrative coherence across `08-VERIFICATION.md`, `STATE.md`, and `v1.0-MILESTONE-AUDIT.md` | milestone-audit-chain | Artifact presence alone cannot guarantee the written verdicts and residual-risk wording are semantically consistent | Read all three artifacts after execution and confirm they tell one consistent closure story without reopening already-closed Phase 9 or 10 gaps |

---

## Validation Sign-Off

- [x] All tasks have direct automated artifact checks; no Wave 0 placeholders remain
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
