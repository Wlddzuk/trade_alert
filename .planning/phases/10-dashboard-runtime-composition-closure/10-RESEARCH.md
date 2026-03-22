# Phase 10 Research: Dashboard Runtime Composition Closure

**Date:** 2026-03-22
**Phase:** 10
**Scope:** FLOW-06
**Confidence:** HIGH

## Research Goal

Answer what the planner needs to know to close the remaining `FLOW-06` integration gap: the served dashboard exists, but the default runtime composition is still not milestone-ready.

This phase is not about inventing new dashboard features or redesigning the read-only surface. It is about making the shipped app compose usable dashboard auth plus real monitoring/review data at the default served boundary, then proving that behavior through milestone-ready verification.

## What Already Exists

### Served dashboard routes already exist

- `backend/app/main.py` already dispatches dashboard paths separately from Telegram webhook paths.
- `backend/app/api/dashboard_routes.py` already serves:
  - `/dashboard`
  - `/dashboard/login`
  - `/dashboard/logs`
  - `/dashboard/trades`
  - `/dashboard/pnl`
- `backend/app/api/dashboard_auth.py` already provides a lightweight password and session-cookie gate.
- `backend/app/api/dashboard_runtime.py` already provides stale-snapshot fallback behavior.

Phase 10 should not re-plan route registration, page rendering, or auth mechanics from scratch.

### Read models for dashboard content already exist

- `backend/app/ops/overview_service.py` builds the status-first operations overview from trust, scanner-loop, and alert-delivery snapshots.
- `backend/app/ops/incident_log.py` builds the incident/recent failures report.
- `backend/app/audit/review_service.py` builds completed-trade review feeds from lifecycle events.
- `backend/app/audit/pnl_summary.py` builds paper P&L from the same lifecycle events.

Phase 10 should reuse these read models rather than invent parallel dashboard-only models.

### Real runtime-owned state already exists in pieces

- `LifecycleLog` is a mutable runtime event source already used by the Telegram operator path.
- `TelegramDeliveryState` and `TelegramRuntimeDeliveryService` already produce delivery outcomes and attempts.
- `CandidateFeedService` already exists as the scanner/runtime-facing seam for qualifying setup emission.

The gap is not absence of domain models. The gap is that the default served app does not compose the dashboard from those runtime-owned sources.

## Current Gap

### The default app still serves synthetic dashboard data

`backend/app/api/dashboard_runtime.py` currently builds the default snapshot from:

- a synthetic `SystemTrustSnapshot` with `provider_statuses=()`
- `IncidentLogService().build(())`
- `TradeReviewService().build_completed_trade_feed(())`
- `PnlSummaryService().build((), today=observed_at)`

That is structurally correct but operationally empty. Overview, logs, trades, and P&L all render, but they are not fed by the real running system.

### The default app still has no usable auth configuration

`backend/app/main.py` exports `app = create_app()`.

`create_app()` only wires dashboard auth if `dashboard_auth_settings` is explicitly injected. Otherwise the dashboard stays fail-closed and returns `503 Dashboard access is not configured.`

That behavior is fine as a safety default, but it means milestone verification cannot treat the default served app as a usable operator review surface yet.

### Existing verification proves route serving, not default runtime composition

Current dashboard tests prove:

- route dispatch works
- login/session behavior works
- stale fallback works
- each section renders through the served app boundary

But the important test seam still injects both:

- custom `DashboardAuthSettings`
- custom `DashboardRuntimeSnapshotProvider`

That means the milestone still lacks proof that the shipped default app composes a real dashboard runtime on its own.

## What The Planner Must Decide

### 1. What owns dashboard runtime composition?

The main planning question is not how to render a dashboard. It is where the app should source real runtime state from when `create_app()` is used without test-only injection.

The planner should decide whether to:

- introduce a dedicated runtime container for shared operator state, or
- add a dashboard runtime composition factory that consumes existing shared state objects.

Either way, the dashboard must stop constructing empty tuples internally and instead consume runtime-owned sources.

### 2. What is the canonical source for review and P&L?

This is the clearest gap.

The real source already appears to be `LifecycleLog`, because:

- Telegram alert emission can record pre-entry alerts there
- operator approvals and adjustments record decisions there
- broker opens/closes record trade lifecycle there
- trade review and P&L services already consume lifecycle events

The planner should treat `LifecycleLog` as the canonical runtime audit source unless code inspection during planning reveals a stronger persistence seam.

Implication:

- dashboard review and P&L should be built from the same shared `LifecycleLog` instance used by the runtime operator workflow
- Phase 10 should not add a second review-event store

### 3. What is the canonical source for overview and incident snapshots?

This is the largest remaining ambiguity.

The overview surface needs real values for:

- `SystemTrustSnapshot`
- scanner-loop heartbeat
- alert-delivery health
- recent incidents / resolved incidents

The codebase has the builders for these concepts, but the default app does not yet have a shared runtime-owned state object that exposes them together.

The planner needs to determine whether Phase 10 should:

- compose directly from a small set of runtime stores already present but not yet unified, or
- introduce one narrow `dashboard_runtime_state` seam that aggregates:
  - current trust snapshot
  - scanner loop snapshot
  - alert-delivery attempts/snapshot
  - system events / incidents
  - lifecycle log

The second option is more likely to plan cleanly because it centralizes the remaining integration work without changing the dashboard route layer.

### 4. Where should auth configuration come from?

Phase 10 needs usable default auth at the served runtime boundary, but should not expand into a general auth system.

The planner should pick one explicit configuration source for:

- dashboard password
- session secret

The likely shape is environment-backed app configuration resolved during default app composition.

What matters for planning:

- `DashboardAuthSettings` should remain the route-layer contract
- the default app should populate it from configuration instead of requiring test or ad hoc injection
- missing config should still fail closed
- milestone verification should exercise the real config-loading path

### 5. How should the served app expose a milestone-ready runtime assembly path?

Right now there are effectively two worlds:

- the default served app for dashboard routes
- the Telegram operator runtime factory for live workflow state

Phase 10 likely needs one composition story that makes them share the same runtime state instead of treating dashboard and Telegram as disconnected entrypoints.

The planner should explicitly answer whether:

- `create_app()` becomes the milestone-ready shared composition path, or
- a new default runtime factory becomes the primary shipped boundary and `app = ...` delegates to it.

Without that decision, the plan risks patching the dashboard in isolation while leaving the app composition model incoherent.

## Concrete Artifact Wiring

- `backend/app/main.py:create_app()` should be the default served-boundary composition root for Phase 10.
- `backend/app/config.py` should load the environment-backed dashboard password and session secret that `backend/app/api/dashboard_auth.py` already expects through `DashboardAuthSettings`.
- `backend/app/main.py:create_app()` should pass those resolved auth settings into the existing dashboard auth seam instead of requiring caller injection.
- `backend/app/api/dashboard_runtime.py` should own the runtime snapshot composition seam used by dashboard routes.
- That runtime seam should read monitoring inputs from the existing ops read-model sources used for overview and incident presentation, rather than manufacturing empty tuples internally.
- That runtime seam should read trade-review and paper-P&L inputs from the shared `backend/app/audit/lifecycle_log.py` source that already feeds the audit read models.
- `backend/tests/dashboard/test_dashboard_runtime_state.py`, `backend/tests/dashboard/test_dashboard_auth.py`, and `backend/tests/dashboard/test_dashboard_serving.py` are the primary served-boundary proof artifacts for default composition and auth bootstrap.
- `backend/tests/dashboard/test_dashboard_review_and_logs.py`, `backend/tests/dashboard/test_dashboard_overview.py`, `backend/tests/audit_review/test_trade_review_groups.py`, and `backend/tests/audit_review/test_pnl_summary.py` are the primary proof artifacts that the default runtime seam is wired to real monitoring/review sources instead of placeholders.

## Standard Stack

- Keep the custom ASGI app boundary in `backend/app/main.py`.
- Keep `DashboardRoutes` thin and HTTP-focused.
- Keep `DashboardRuntimeSnapshotProvider` as the route-facing dashboard snapshot seam.
- Reuse:
  - `OperationsOverviewService`
  - `IncidentLogService`
  - `TradeReviewService`
  - `PnlSummaryService`
  - `LifecycleLog`
- Add one narrow runtime composition/state seam rather than introducing a framework migration or a second web app.

## Architecture Patterns

### Pattern 1: Thin route layer, owned composition at app boundary

`DashboardRoutes` should continue to:

- handle path/method/auth checks
- request one runtime snapshot
- render HTML

It should not become the owner of monitoring state, lifecycle event storage, or config lookup.

### Pattern 2: Shared runtime stores, derived dashboard read models

Dashboard inputs should come from shared runtime-owned stores, then be transformed into operator-facing read models on request.

This keeps:

- Telegram workflow state
- monitoring state
- audit/review state

consistent across both operator surfaces.

### Pattern 3: One canonical runtime snapshot builder for all dashboard sections

Overview, logs, trades, and P&L should still be assembled into one `DashboardRuntimeSnapshot`, but the snapshot builder must read from real runtime dependencies rather than placeholder tuples.

This preserves the existing stale-fallback behavior and keeps the renderer contract stable.

## Don't Hand-Roll

- Do not introduce a separate frontend stack for this phase.
- Do not rebuild trade review or P&L logic inside dashboard code.
- Do not create a second audit/review event store if `LifecycleLog` can remain the canonical source.
- Do not add user accounts, roles, or generalized auth middleware.
- Do not compute dashboard data independently inside route handlers.

## Common Pitfalls

### 1. Fixing the dashboard in tests but not in the default app

This phase fails if route tests still depend on injected auth and snapshot providers while `app = create_app()` remains operationally empty.

### 2. Wiring only review/P&L and leaving overview/logs synthetic

The phase scope includes real monitoring/review snapshot providers, not just removal of placeholder trade data.

### 3. Creating dashboard-only state that diverges from Telegram runtime state

If dashboard review uses a different event source than the Telegram operator workflow, `FLOW-06` becomes visually convincing but architecturally false.

### 4. Smuggling in framework or product-shell scope

This is a runtime-composition closure phase, not a FastAPI migration, SPA build, or dashboard redesign.

### 5. Proving section reachability without proving milestone readiness

Phase 7 already proved that routes exist. Phase 10 must prove that the default served runtime is usable and integrated.

## Validation Architecture

This section is justified because the phase exists to close a milestone integration gap, not just ship code.

### Validation target

Verification must answer:

- does the default served app load usable dashboard auth config?
- does the default served app assemble dashboard snapshots from real runtime-owned sources?
- do served overview/logs/trades/P&L routes reflect shared runtime state rather than placeholder data?
- does stale fallback still work after real runtime composition is introduced?

### Required automated proof

The validation plan should include:

- default-app auth proof:
  - the default app can authenticate when runtime config is present
  - the default app still fails closed when required config is absent
- default-app review proof:
  - lifecycle events created through the real runtime path appear in served `/dashboard/trades`
  - the same events drive served `/dashboard/pnl`
- default-app monitoring proof:
  - served overview/logs reflect runtime trust, incidents, scanner-loop health, and alert-delivery state from shared sources
- stale proof:
  - last-successful snapshot fallback still works with the real snapshot builder

### Preferred verification style

Use served-boundary integration tests that begin from shipped composition paths, not renderer-only tests and not snapshot-provider injection except where specifically needed to force stale failures.

The key assertion for Phase 10 is not “the dashboard can render.” It is “the shipped default runtime composes the dashboard from live application state.”

## Code Examples

### Existing placeholder seam to replace

`backend/app/api/dashboard_runtime.py`

```python
return DashboardRuntimeSnapshot(
    overview=overview_service.build_overview(trust_snapshot),
    incident_report=IncidentLogService().build(()),
    review_feed=TradeReviewService().build_completed_trade_feed(()),
    pnl_summary=PnlSummaryService().build((), today=observed_at),
    last_updated_at=observed_at,
)
```

Planning implication: Phase 10 should preserve the `DashboardRuntimeSnapshot` contract while replacing these empty inputs with runtime-owned sources.

### Existing shared review/P&L derivation seam to reuse

`backend/app/audit/review_service.py` and `backend/app/audit/pnl_summary.py`

```python
review_feed = TradeReviewService().build_completed_trade_feed(log.all_events())
pnl_summary = PnlSummaryService().build(log.all_events(), today=date(2026, 3, 17))
```

Planning implication: the dashboard should consume the shared lifecycle log the same way the renderer tests already do.

## Likely Plan Shape

### Plan 10-01: Default runtime composition and auth wiring

Focus:

- decide and implement the default config source for dashboard auth
- add the shared runtime composition seam for dashboard dependencies
- make the default served app compose real dashboard auth and snapshot providers

### Plan 10-02: Real snapshot providers and milestone verification

Focus:

- replace placeholder review/P&L inputs with shared lifecycle-backed data
- wire overview/logs to real runtime monitoring sources
- add served-boundary tests that prove default runtime composition for `FLOW-06`

## Open Questions For Planning

- Is there already an in-memory or persistent runtime source for trust snapshots, scanner-loop heartbeats, and system events that Phase 10 can compose, or does this phase need to introduce that narrow state seam?
- Should the milestone-ready default app and the Telegram operator runtime converge on one factory in this phase, or is a shared dependency container enough?
- What exact environment/config contract should own dashboard password and session-secret defaults?
- Which served-boundary test should be treated as the milestone citation proving “default app composition,” not just route reachability?

## Recommended Planning Stance

Plan Phase 10 as a runtime-composition closure with two deliverables:

- one composition deliverable that unifies dashboard auth and shared runtime state at the default served boundary
- one verification deliverable that proves `FLOW-06` against that default boundary, not against injected fixtures

If planning stays narrower than that, the milestone audit gap will likely remain open.
