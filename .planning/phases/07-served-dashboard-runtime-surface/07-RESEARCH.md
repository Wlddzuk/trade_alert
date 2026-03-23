# Phase 7 Research: Served Dashboard Runtime Surface

**Date:** 2026-03-18
**Phase:** 07
**Scope:** FLOW-06
**Confidence:** HIGH

## Research Goal

Answer what the planner needs to know to turn the existing read-only dashboard composition into a served runtime HTTP surface with route registration, lightweight auth, runtime refresh behavior, and route-level verification.

## What Already Exists

### Dashboard composition already exists

- `backend/app/api/dashboard_routes.py` already provides:
  - `build_overview_model(...)`
  - `render_overview_page(...)`
  - `render_dashboard_page(...)`
- `backend/app/dashboard/renderers.py` already renders backend HTML for:
  - overview
  - logs
  - trade review
  - paper P&L
- Existing dashboard tests already lock important product constraints:
  - read-only labeling
  - overview-first content
  - logs/review/P&L sections
  - absence of forms and action buttons

### A minimal served app boundary already exists

- `backend/app/main.py` already exposes `BuySignalApp` as an ASGI callable.
- Phase 6 already proved the app boundary can be tested directly through ASGI-level request simulation.
- `backend/tests/operator_workflow/test_telegram_webhook_serving.py` is the key validation precedent for Phase 7:
  - request enters ASGI app
  - route dispatch occurs inside the served boundary
  - behavior is validated at the application surface instead of by direct helper invocation

### Read models already exist for dashboard content

- Ops overview can already be built from:
  - `OperationsOverviewService`
  - `IncidentLogService`
- Audit review and P&L can already be built from:
  - `TradeReviewService`
  - `PnlSummaryService`
  - `LifecycleLog`

That means Phase 7 should not invent new dashboard content models. It should wire runtime routes to these existing read-model seams.

## Current Gaps

### The app boundary only returns JSON and only delegates to Telegram

Right now `BuySignalApp.__call__` does three things:

1. read the request body
2. hand the request to `telegram.handle_http_request(...)`
3. serialize the result as JSON

There is no app-level route dispatch between Telegram and dashboard paths, and there is no HTML response path at all.

### Dashboard routes are not runtime routes yet

`DashboardRoutes` is currently a composition helper, not an HTTP routing layer. It can render HTML strings from already-built models, but it does not:

- inspect method/path
- authenticate a browser session
- redirect `/` to the dashboard
- serve section-specific routes
- return 404 pages
- emit refresh-related headers or page metadata

### No runtime snapshot assembler exists

The tests construct overview, incident, review, and P&L inputs directly. The served app has no runtime-facing object that can answer:

- what is the current operations snapshot?
- what recent incidents should the dashboard show?
- what lifecycle events feed review and P&L?
- what timestamp should the dashboard expose as “last updated”?

Phase 7 therefore needs a dashboard runtime data seam, not just route strings.

### Auth/session behavior is entirely absent

The phase context locks in:

- simple password gate
- browser-session reuse after successful auth
- fail-closed behavior on missing or wrong credentials

None of that exists in current route or app code. Phase 7 needs a minimal authentication/session boundary before dashboard content is rendered.

### Refresh and stale handling are not represented

The renderers currently return static HTML with no runtime freshness affordance. Phase 7 needs a practical way to expose:

- a visible last-updated timestamp
- auto-refresh around every 30 seconds
- stale warning behavior when runtime refresh/snapshot assembly fails
- preservation of the last successful snapshot during refresh failures

## Planning Implications

### Phase 7 should be planned around three distinct seams

#### 1. App-boundary routing and HTML response support

The first plan should extend `BuySignalApp` from “Telegram JSON endpoint only” into a small multi-route ASGI app that can:

- dispatch dashboard paths separately from Telegram webhook paths
- return HTML responses for dashboard pages
- redirect `/` into the overview route
- render a dashboard-specific 404 page for mistyped dashboard URLs
- preserve Telegram behavior unchanged

This is foundational because the current app boundary cannot serve HTML at all.

#### 2. Dashboard runtime snapshot and auth/session wiring

The second plan should introduce a runtime-facing dashboard service layer responsible for:

- assembling current overview + incident data
- assembling review + P&L data from lifecycle events
- shaping a page/snapshot contract that includes freshness metadata
- enforcing password/session access before content is shown

This is the real runtime seam of the phase. Without it, routes would still depend on test-style direct object construction.

#### 3. Served review-flow behavior and route-level verification

The third plan should prove that operators can use the dashboard through the served boundary, not just via renderer calls. That means:

- route-level tests for overview/logs/review/P&L access
- redirect/auth/not-found behavior
- verification that content comes through the runtime app boundary
- evidence beyond composition-only tests

This plan should also cover runtime refresh/stale scenarios because those are served-surface concerns, not pure renderer concerns.

## Implementation Seams

### 1. Keep `DashboardRoutes` thin and HTTP-aware, not domain-heavy

`DashboardRoutes` is the natural place to add dashboard path handling, but it should stay thin. It should not become the owner of trust evaluation, incident construction, trade review derivation, or lifecycle storage. Those responsibilities already belong elsewhere.

Recommended shape:

- keep current model-building/rendering helpers
- add a route-handling entrypoint for dashboard HTTP requests
- delegate snapshot assembly to a dedicated runtime provider/service
- delegate auth/session checks to a small dashboard auth helper

### 2. Introduce a dashboard runtime provider/snapshot service

The missing seam is a runtime source of truth that the app can call on every request. It should provide one stable interface for:

- overview snapshot
- incident snapshot
- review feed
- P&L summary
- `last_updated`
- whether the snapshot is fresh or stale

The main goal is to separate “where dashboard data comes from” from “how it is routed/rendered.”

### 3. Response typing needs to widen beyond Telegram JSON

`TelegramRoutes.handle_http_request(...)` currently returns a JSON-oriented response model. Phase 7 will likely need either:

- a shared response type that supports JSON and HTML, or
- separate Telegram and dashboard response types with app-level branching

The planner should make this explicit early. If the app stays JSON-only internally, dashboard serving will become awkward and brittle.

### 4. Session auth should stay minimal and local to the dashboard boundary

The phase context does not justify a general auth framework. The pragmatic seam is:

- password comparison against configured credentials
- signed or opaque session cookie after success
- logout optional but lightweight
- fail closed on missing config or bad password

This auth layer should apply only to dashboard routes and should not bleed into Telegram webhook handling.

### 5. Route structure should mirror the user’s mental model

The route boundary should remain sectioned and read-only:

- overview-first landing route
- separate logs route
- separate trade-review route
- separate paper-P&L route

That keeps runtime navigation aligned with Phase 5’s information architecture instead of forcing one monolithic page contract.

### 6. Refresh behavior should be implemented as runtime-page behavior, not renderer-only decoration

The phase context requires observable runtime freshness and stale-state handling. The implementation seam should support:

- successful request renders with current snapshot and timestamp
- failed refresh/snapshot build reuses last successful snapshot if available
- stale marker is injected into the rendered surface

The planner should avoid tying stale behavior to client-side JavaScript state only. The server should remain the source of truth for freshness.

## Risks

### 1. Scope drift into a full web framework migration

The current app is a custom ASGI callable. Phase 7 only needs a small HTTP surface, not a framework migration. Planning should avoid quietly turning this into “adopt FastAPI/Starlette and rebuild routing/auth/templates.”

### 2. Pulling Phase 8 monitoring scope forward

FLOW-06 is about served runtime reachability of an already-defined dashboard. Phase 7 should not expand into new monitoring signals, new ops metrics, or broader observability architecture that belongs to OPS requirements in Phase 8.

### 3. Recomputing dashboard content instead of reusing Phase 5 read models

If runtime routes rebuild trust logic or audit grouping ad hoc, the served dashboard can diverge from the existing composition tests. The route layer should consume existing services, not reinterpret them.

### 4. Overcomplicating auth

The locked decision is a simple password gate. Planning a user system, role model, database-backed sessions, or broad auth middleware would be hidden scope and would slow the phase without improving the v1 outcome.

### 5. No stable story for runtime data dependencies

The biggest technical ambiguity is where live system events, alert-delivery failures, and lifecycle events are sourced at request time. If the planner does not define that seam explicitly, route work will stall or hardcode test-only data paths.

### 6. Weak stale-state semantics

The context explicitly says failed refresh should preserve the last successful snapshot while warning that the page is stale. If the plan only adds auto-refresh timing and timestamp text, it will miss the actual operator-trust requirement.

## Likely Plan Decomposition

## Plan 07-01: Served dashboard app boundary and route registration

Focus:

- extend `BuySignalApp` to dispatch dashboard routes alongside Telegram routes
- add HTML response support
- redirect `/` to the overview route
- return dashboard-specific not-found content for bad dashboard URLs

Likely files:

- `backend/app/main.py`
- `backend/app/api/dashboard_routes.py`
- new/updated response helpers under `backend/app/api/`
- new route-level tests under `backend/tests/dashboard/`

## Plan 07-02: Dashboard runtime snapshot + password/session gate

Focus:

- introduce runtime snapshot provider/service for overview, incidents, review, and P&L
- add lightweight password auth and browser-session reuse
- fail closed when credentials are absent or invalid
- expose `last_updated` and stale/fresh state to rendering

Likely files:

- new dashboard runtime/auth modules under `backend/app/dashboard/` or `backend/app/api/`
- `backend/app/api/dashboard_routes.py`
- `backend/app/dashboard/renderers.py`
- route/service tests for auth and snapshot behavior

## Plan 07-03: Served review flow, refresh behavior, and verification evidence

Focus:

- ensure overview/logs/trade-review/P&L are reachable through served routes
- cover auto-refresh and visible freshness metadata
- validate stale fallback behavior using last successful snapshot
- add phase-level evidence beyond composition-only tests

Likely files:

- `backend/tests/dashboard/` for ASGI-level access tests
- possibly targeted runtime fixtures/fakes for snapshot failure simulation
- summary/evidence docs generated during execution

## Verification Recommendations

### Keep composition tests, but stop relying on them as primary evidence

The existing dashboard tests are still useful for fast HTML/content regressions. They should remain. But Phase 7 needs new tests that prove runtime reachability through `create_app(...)` and the ASGI boundary.

### Add route-level tests modeled after Phase 6 webhook tests

Recommended coverage:

- unauthenticated dashboard request is denied
- valid login establishes a browser session
- authenticated request to overview returns HTML content
- `/` redirects to the overview route
- logs, trade review, and P&L routes return the expected read-only content
- mistyped dashboard path returns dashboard-specific 404 content
- Telegram webhook routes still behave as before

### Add stale/failure-path verification

Recommended coverage:

- runtime snapshot provider succeeds and emits a `last_updated` timestamp
- subsequent snapshot failure reuses the last good snapshot
- stale warning renders when fallback snapshot is used
- initial request with no valid snapshot fails closed instead of serving misleading content

### Keep the auth checks narrow and explicit

Recommended coverage:

- missing password config denies access
- wrong password denies access
- authenticated browser session survives subsequent page navigation
- session protection is scoped to dashboard routes and does not interfere with Telegram webhook handling

## Validation Architecture

- Keep the phase fully automated under `pytest`.
- Retain current composition tests:
  - `backend/tests/dashboard/test_dashboard_overview.py`
  - `backend/tests/dashboard/test_dashboard_review_and_logs.py`
- Add ASGI-level dashboard serving tests adjacent to the Phase 6 webhook style:
  - new tests for HTML route serving through `create_app(...)`
  - new tests for auth/session flow
  - new tests for redirect/not-found behavior
  - new tests for stale snapshot fallback
- Prefer fake in-memory runtime providers and fake auth config in tests rather than introducing external dependencies.
- Phase success evidence should show two layers:
  - composition tests still passing
  - served-boundary tests proving runtime availability

## Open Questions The Planner Should Resolve Early

1. What object owns the runtime dashboard snapshot inputs at request time?
2. Should dashboard routes be one page with anchor sections, or separate served pages per section?
3. What exact cookie/session mechanism is acceptable for the “authenticate once per browser session” constraint?
4. Where should the last successful dashboard snapshot live so stale fallback is deterministic and testable?
5. How much of the refresh behavior should be HTML meta refresh versus lightweight client-side script?

## Recommended Planning Stance

Plan Phase 7 as runtime delivery over existing dashboard content, not as dashboard redesign. The critical work is:

- widening the ASGI app from Telegram-only JSON into mixed JSON/HTML route serving
- introducing a minimal authenticated dashboard runtime seam
- proving operators can review status, logs, and completed paper trades through the served boundary with automated evidence

That keeps the phase tightly aligned with FLOW-06 and avoids dragging in hidden frontend or observability scope.
