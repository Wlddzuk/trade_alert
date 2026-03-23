# Phase 8 Research: Monitoring Verification Recovery

**Date:** 2026-03-19
**Phase:** 08
**Scope:** OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Confidence:** HIGH

## Research Goal

Answer what the planner needs to know to recover the missing Phase 5 verification artifact without reopening product scope. The work is evidence synthesis and audit traceability over shipped code, shipped tests, and Phase 7 served-dashboard proof.

## What Already Exists

### The audit gap is explicit and narrowly scoped

- `.planning/v1.0-MILESTONE-AUDIT.md` already identifies the blocking issue:
  - `05-VERIFICATION.md` is missing
  - `OPS-01` through `OPS-05` are treated as partial only because the verification artifact is absent
  - the milestone verification flow breaks at evidence aggregation, not feature behavior

### Phase 5 already shipped the required behaviors

- `05-01-SUMMARY.md` maps:
  - `OPS-01` degraded or untrusted state visibility
  - `OPS-02` scanner loop health monitoring
  - `OPS-05` error and alert-failure visibility
- `05-02-SUMMARY.md` maps:
  - `OPS-03` immutable audit review
  - `OPS-04` paper P&L summaries
- `05-03-SUMMARY.md` maps:
  - read-only dashboard composition over those Phase 5 read models

### Phase 7 already provides the runtime evidence chain that Phase 5 was missing

- `07-VERIFICATION.md` proves the dashboard is now reachable through the served ASGI boundary.
- That runtime proof is the right supporting evidence for review access and dashboard observability, but it should be cited as downstream confirmation rather than replacing the original Phase 5 ops/audit proof.

## Concrete Evidence Seams In Code

### OPS-01 and OPS-02 and OPS-05: operational monitoring

Primary code:
- `backend/app/ops/monitoring_models.py`
- `backend/app/ops/overview_service.py`
- `backend/app/ops/incident_log.py`
- `backend/app/ops/alert_delivery_health.py`

What these prove:
- current status distinguishes `healthy`, `degraded`, `recovering`, and `offline_session_closed`
- scanner loop health is explicitly modeled as `running`, `stale`, or `idle`
- alert delivery health and recent alert failures are separate, explicit read models
- incidents and resolved trust events are preserved as auditable history

Primary automated evidence:
- `backend/tests/ops_dashboard/test_status_overview.py`
- `backend/tests/ops_dashboard/test_incident_log.py`
- `backend/tests/ops_dashboard/test_alert_delivery_health.py`
- `backend/tests/ops_dashboard/test_telegram_runtime_failures.py`

Why this matters for planning:
- the verification artifact can cite deterministic unit-level proof for every monitoring requirement before it references the served dashboard surface
- `test_telegram_runtime_failures.py` is especially useful for tying alert-delivery failures into operator-visible incidents rather than treating them as isolated low-level records

### OPS-03 and OPS-04: immutable audit review and paper P&L

Primary code:
- `backend/app/audit/review_service.py`
- `backend/app/audit/pnl_summary.py`

What these prove:
- completed trades are reconstructed from immutable lifecycle events
- trade review is grouped by trading day with newest-first ordering
- raw lifecycle events remain secondary drill-down detail
- P&L is today-first and realized-first with cumulative context

Primary automated evidence:
- `backend/tests/audit_review/test_trade_review_groups.py`
- `backend/tests/audit_review/test_pnl_summary.py`

Why this matters for planning:
- the recovered verification report can make a clean requirement-to-test mapping for audit review and P&L without needing additional runtime behavior work

### Served dashboard/runtime proof that should be cited by the recovered Phase 5 report

Primary code:
- `backend/app/api/dashboard_routes.py`
- `backend/app/api/dashboard_runtime.py`
- `backend/app/main.py`

Primary automated evidence:
- `backend/tests/dashboard/test_dashboard_overview.py`
- `backend/tests/dashboard/test_dashboard_review_and_logs.py`
- `backend/tests/dashboard/test_dashboard_serving.py`
- `backend/tests/dashboard/test_dashboard_runtime_state.py`

What these add:
- served route access for overview, logs, trades, and P&L
- read-only UI guarantees
- last-updated and stale-snapshot posture
- route-level proof that the dashboard is operator-accessible as a runtime surface

Planning implication:
- Phase 8 should use this as supporting proof for the final evidence chain, especially where the recovered report needs to show the operator can actually review the surfaced information through the shipped runtime boundary

## Recommended Verification Commands

Fast command set for evidence recovery:

- `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py -q`
- `uv run pytest backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py -q`
- `uv run pytest backend/tests/dashboard/test_dashboard_overview.py backend/tests/dashboard/test_dashboard_review_and_logs.py backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_runtime_state.py -q`

Observed status during research:

- ops dashboard bundle: 9 passed
- audit review bundle: 4 passed
- dashboard bundle: 11 passed

## Best Artifact Shape

The recovered output should be a definitive `.planning/phases/05-monitoring-audit-and-review-surface/05-VERIFICATION.md` with:

1. the original milestone-audit gap stated plainly
2. requirement-by-requirement coverage for `OPS-01` through `OPS-05`
3. code references and automated test references for each requirement
4. a served-dashboard evidence section that cites `07-VERIFICATION.md` where runtime review access matters
5. a short residual-risk section that stays non-blocking and does not reopen scope

The report should read like an audit-ready phase verification artifact, not like a new summary or a recovery memo.

## Suggested Plan Breakdown

## Plan 08-01: Reconstruct the Phase 5 evidence map from shipped code and tests

Focus:
- inspect Phase 5 summaries, UAT, milestone audit findings, and relevant backend modules/tests
- build a requirement-by-requirement evidence inventory for `OPS-01` through `OPS-05`
- identify which evidence is direct Phase 5 proof versus Phase 7 runtime corroboration

Likely files:
- `.planning/phases/05-monitoring-audit-and-review-surface/05-VERIFICATION.md`
- `.planning/phases/08-monitoring-verification-recovery/08-01-SUMMARY.md`

Why this should be first:
- it isolates the factual evidence-gathering task from the final audit-facing writing pass
- it reduces the chance of a vague verification artifact that cites requirements without concrete proof

## Plan 08-02: Publish the recovered verification artifact and close the traceability gap

Focus:
- write the final `05-VERIFICATION.md`
- make explicit requirement coverage for `OPS-01` through `OPS-05`
- cite Phase 7 served-dashboard verification where runtime review access matters
- ensure the final artifact is easy for the milestone audit to reference directly

Likely files:
- `.planning/phases/05-monitoring-audit-and-review-surface/05-VERIFICATION.md`
- `.planning/phases/08-monitoring-verification-recovery/08-02-SUMMARY.md`
- optionally `.planning/v1.0-MILESTONE-AUDIT.md` only if execution decides the audit file should be refreshed after the recovered artifact exists

Why this should stay separate:
- the first plan is evidence assembly
- the second plan is publishing the final verification artifact and traceability closure

## Risks

### 1. Writing a narrative report without requirement-level proof

The biggest failure mode is a polished `05-VERIFICATION.md` that still does not make `OPS-01` through `OPS-05` auditable one by one. The report must map each requirement to code and tests explicitly.

### 2. Treating Phase 7 as a substitute for Phase 5

Phase 7 should strengthen the evidence chain for runtime review access, but Phase 8 still needs to prove the underlying monitoring, audit, and P&L behaviors from Phase 5 artifacts and tests.

### 3. Scope drift into new feature work

Nothing in the evidence reviewed suggests missing product behavior for this phase. The gap is documentation and verification traceability. Planning should avoid adding new monitoring features, new dashboard behavior, or Telegram runtime work.

### 4. Updating milestone audit files too early

The primary deliverable is the recovered `05-VERIFICATION.md`. Any milestone-audit refresh should happen only after that artifact exists and can be cited concretely.

## Validation Architecture

### Test infrastructure

- Framework: `pytest`
- Working directory: repository root
- Quick run command: `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py -q`
- Full phase command: `uv run pytest backend/tests/ops_dashboard/test_status_overview.py backend/tests/ops_dashboard/test_incident_log.py backend/tests/ops_dashboard/test_alert_delivery_health.py backend/tests/ops_dashboard/test_telegram_runtime_failures.py backend/tests/audit_review/test_trade_review_groups.py backend/tests/audit_review/test_pnl_summary.py backend/tests/dashboard/test_dashboard_overview.py backend/tests/dashboard/test_dashboard_review_and_logs.py backend/tests/dashboard/test_dashboard_serving.py backend/tests/dashboard/test_dashboard_runtime_state.py -q`
- Estimated runtime: under 1 second in current local runs

### Sampling strategy

- After any evidence-mapping edits that do not touch backend code: no test rerun required until the verification artifact draft is updated materially
- After any verification-artifact changes that alter cited commands or evidence claims: run the quick command
- Before phase verification: run the full command

### Coverage intent

- `OPS-01`: degraded or untrusted visibility through overview status and trust-state tests
- `OPS-02`: scanner loop health through overview-service and status-overview tests
- `OPS-03`: immutable trade lifecycle review through review-service tests
- `OPS-04`: realized-first paper P&L through P&L summary tests
- `OPS-05`: incident and alert-failure visibility through incident-log and alert-delivery tests, with served dashboard review as supporting proof

### Manual-only verification

Keep any manual check lightweight:
- optional browser or ASGI sanity check that the served dashboard still exposes overview/logs/trades/P&L as read-only routes

This should remain secondary because the repo already has strong automated proof for the relevant behaviors.

## Planner Bottom Line

Phase 8 should plan as two plans, not one:

- first assemble and lock the evidence map for `OPS-01` through `OPS-05`
- then publish the recovered `05-VERIFICATION.md` as the single audit-facing artifact that closes the milestone gap

The evidence base is already strong. The missing piece is precise synthesis and traceability.
