# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Buy Signal MVP

**Shipped:** 2026-03-22
**Phases:** 11 | **Plans:** 31 | **Sessions:** 7 recorded execution days

### What Was Built
- Provider abstractions, scan-universe rules, runtime windows, and explicit trust-state degradation and recovery handling.
- Ranked momentum-pullback scanner projections with validity, triggers, invalidations, and operator-facing reasons.
- Telegram-led paper-trading workflow with approvals, adjustments, risk gates, deterministic exits, and immutable lifecycle audit logging.
- Served read-only dashboard coverage for overview, logs, trade review, and paper P&L, backed by runtime-owned state at the default app boundary.
- Milestone audit closure for emitted-alert continuity, recovered verification artifacts, and archival-ready planning traceability.

### What Worked
- The phase-and-plan structure kept milestone scope explicit and made verification gaps narrow enough to close cleanly late in the milestone.
- Audit-facing summaries and verification artifacts made it practical to reconcile milestone truth without reopening shipped runtime scope.

### What Was Inefficient
- Several closure tasks were documentation and verification recovery work caused by earlier planning-state drift rather than new product delivery.
- Parallel git staging and commit attempts occasionally raced on `.git/index.lock`, which forced serial retries during plan execution.

### Patterns Established
- Keep runtime behavior proof anchored to canonical verification artifacts instead of duplicating evidence in later closure phases.
- Use emitted-alert-first and served-boundary proofs when milestone claims depend on real runtime continuity rather than seam-level behavior alone.

### Key Lessons
1. Milestone audits stay cheap only when roadmap, requirements, summaries, and verification artifacts are kept aligned as features land.
2. Thin served boundaries plus runtime-owned shared state let review surfaces stay truthful without introducing a second control plane.

### Cost Observations
- Model mix: Not explicitly tracked in-project for v1.0
- Sessions: 7 recorded execution days
- Notable: Late milestone cost shifted from feature work to evidence recovery and traceability cleanup, which is avoidable in the next milestone.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 7 recorded execution days | 11 | Established end-to-end phase planning, verification, and milestone audit closure patterns |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | Verification-backed; exact total not aggregated here | Not centrally tracked | Multiple backend-only planning and runtime slices shipped without adding a second frontend stack |

### Top Lessons (Verified Across Milestones)

1. Evidence-backed phase summaries make milestone closure substantially easier than reconstructing intent from code alone.
2. Operator-facing review surfaces should compose shared runtime state rather than invent separate audit-only data paths.
