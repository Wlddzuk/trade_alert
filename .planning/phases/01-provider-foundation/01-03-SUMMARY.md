---
phase: 01-provider-foundation
plan: 03
subsystem: infra
tags: [python, freshness, trust-state, monitoring, pytest]
requires:
  - phase: 01-provider-foundation
    provides: runtime window semantics and normalized provider health snapshots
provides:
  - capability-specific provider freshness evaluation
  - actionable trust-state transitions across healthy, degraded, and recovering
  - provider trust events for later operator-facing surfaces
affects: [phase-02, phase-04, phase-05]
tech-stack:
  added: []
  patterns: [capability-specific-freshness-thresholds, explicit-trust-state-transitions]
key-files:
  created:
    - backend/app/ops/health_models.py
    - backend/app/ops/provider_health.py
    - backend/app/ops/degraded_state.py
    - backend/app/ops/system_events.py
  modified:
    - backend/tests/provider_foundation/test_provider_health.py
key-decisions:
  - "Capability-specific freshness thresholds are enforced through a dedicated provider-health evaluator instead of being embedded in adapters."
  - "Outside-window inactivity never produces a stale-feed failure or degraded trust state."
  - "Trust restoration uses an explicit recovering state so actionable output stays blocked until a clean recovery pass is observed."
patterns-established:
  - "Provider freshness is evaluated before any scanner logic consumes market or news inputs."
  - "System trust state is derived from provider freshness snapshots rather than raw vendor timestamps."
  - "Operator-facing degraded and recovery notifications can be built later on top of explicit system event objects."
requirements-completed: [DATA-03, DATA-04]
duration: 3 min
completed: 2026-03-14
---

# Phase 1: Provider Foundation Summary

**Provider freshness evaluation with degraded/recovering trust-state transitions and explicit recovery events**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T09:59:12Z
- **Completed:** 2026-03-14T10:01:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added provider-health models and freshness rules that evaluate market-data and news feeds against independent thresholds while honoring the ET runtime window.
- Added a trust-state monitor that derives one system-level actionable state from provider freshness and blocks partial actionable output when either feed becomes stale.
- Added explicit system events for degraded, recovering, and trust-restored transitions plus automated coverage for stale-feed gating and recovery behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement per-provider freshness tracking and health snapshots** - `7f36d72` (feat)
2. **Task 2: Implement degraded-state and recovery event logic for actionable trust** - `b3848c4` (feat)

## Files Created/Modified

- `backend/app/ops/health_models.py` - provider freshness rules plus system trust snapshot models
- `backend/app/ops/provider_health.py` - freshness evaluation logic scoped to provider capability and runtime state
- `backend/app/ops/degraded_state.py` - system-level trust monitor and degraded/recovery transitions
- `backend/app/ops/system_events.py` - explicit degraded, recovering, and trust-restored event contracts
- `backend/tests/provider_foundation/test_provider_health.py` - end-to-end health, degraded-state, and recovery coverage

## Decisions & Deviations

- Used capability-specific freshness thresholds so market data and news can fail independently without leaking provider details into downstream phases.
- Kept outside-window evaluation healthy but non-actionable so stale timestamps after-hours do not undermine operator trust.
- Added an explicit `recovering` transition to make trust restoration observable and testable before scanner output resumes.
- No deviations from the plan scope were needed once Task 1 established the provider freshness boundary.

## Next Phase Readiness

- Phase 2 can gate scanner candidate generation on a single actionable-trust snapshot instead of reasoning about feed staleness ad hoc.
- Later workflow and monitoring phases can surface degraded/recovery notifications by consuming the `SystemEvent` contract instead of re-deriving state.
- No blockers remain for moving into Phase 2 planning and execution.
