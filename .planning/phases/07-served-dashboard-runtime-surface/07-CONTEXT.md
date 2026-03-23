# Phase 7: Served Dashboard Runtime Surface - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing secondary read-only dashboard reachable through a served HTTP application boundary instead of render-only composition code.

This phase decides how operators reach and use the served dashboard at runtime. It does not redesign the Phase 5 dashboard information architecture, add trade controls, or turn the dashboard into a primary workflow surface.

</domain>

<decisions>
## Implementation Decisions

### Access posture
- The served dashboard is for a single operator in v1.
- The HTTP boundary should require a simple password before dashboard content is shown.
- The operator should only need to authenticate once per browser session rather than on every page view.
- If credentials are missing or wrong, the app must fail closed and deny dashboard access.

### Route shape
- The served dashboard should land on an overview-first page.
- Logs, trade review, and paper P&L should each have their own read-only runtime route under the dashboard boundary.
- The application root `/` should redirect into the dashboard rather than acting as a separate product surface.
- Mistyped dashboard URLs should render a helpful dashboard-specific not-found page with a route back to the overview.

### Refresh behavior
- The served dashboard should auto-refresh while open.
- Default refresh cadence should be every `30 seconds`.
- The page should show a visible `last updated` timestamp so the operator can judge freshness at a glance.
- If runtime refresh fails, the dashboard should keep showing the last successful data snapshot but mark the page stale with a warning.

### Device posture
- The served dashboard should be optimized for desktop or laptop use first.
- Phone access should still work, but primarily for quick runtime status checks rather than deep review.
- The visual density should stay compact but readable rather than becoming a raw console or a spacious marketing-style layout.
- On smaller screens, completed-trade review should start from collapsed day groups and concise summaries, with deeper detail available on expansion.

### Already-fixed inputs that Phase 7 must honor
- The dashboard remains secondary and read-only in v1.
- The overview remains status-first, with separate read-only surfaces for logs, trade review, and paper P&L.
- Telegram remains the primary operator workflow and the dashboard must not become a second control plane.
- Phase 7 is about served runtime delivery of the existing dashboard surface, not about adding new review capabilities.

### Claude's Discretion
- Exact password prompt copy, session-cookie mechanics, and logout affordance, as long as access stays lightweight and fail-closed.
- Exact dashboard URL names under the served boundary, as long as overview lands first and the other sections keep separate routes.
- Exact auto-refresh implementation and timestamp formatting, as long as refresh stays visible, roughly `30 seconds`, and stale-state handling preserves context.
- Exact responsive layout treatment and breakpoint details, as long as desktop remains primary and mobile remains usable for quick review.

</decisions>

<specifics>
## Specific Ideas

- The served app should feel like an operational runtime boundary, not a separate product shell.
- Opening the root of the app should take the operator straight into the dashboard flow rather than forcing an extra landing step.
- The runtime surface should remain safe during incidents by keeping the last known data visible while clearly warning when refresh is stale.
- Mobile support should preserve quick trust and review checks without trying to rival the desktop review experience.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/main.py`
  - Already provides a thin ASGI application boundary that can be extended to route dashboard HTTP requests instead of only Telegram webhook traffic.
- `backend/app/api/dashboard_routes.py`
  - Already builds the overview and full dashboard page models, which Phase 7 can expose through real HTTP paths.
- `backend/app/dashboard/renderers.py`
  - Already renders the read-only HTML for overview, logs, trade review, and paper P&L sections.
- `backend/tests/dashboard/test_dashboard_overview.py`
  - Already verifies the status-first, read-only overview composition expected to remain the landing experience.
- `backend/tests/dashboard/test_dashboard_review_and_logs.py`
  - Already verifies the full read-only dashboard composition for logs, review, and P&L content.

### Established Patterns
- The codebase already favors thin backend-rendered surfaces over introducing a separate frontend stack.
- Telegram route handling in `backend/app/api/telegram_routes.py` and `backend/app/main.py` shows the current application-level routing style Phase 7 should extend rather than replace.
- Prior phases already fixed the dashboard as observational only, summary-first, and secondary to Telegram.
- Existing dashboard renderers produce HTML only; Phase 7 needs to add served routing and runtime access behavior on top of those renderers.

### Integration Points
- Phase 7 should add dashboard route dispatch to the served application boundary in `backend/app/main.py`.
- Runtime dashboard routes should connect existing overview, incident, trade-review, and P&L read models to actual HTTP responses rather than direct test-only renderer invocation.
- Verification should exercise dashboard access through the served app boundary, similar to how Phase 6 already verifies Telegram webhook behavior through ASGI-level tests.

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-served-dashboard-runtime-surface*
*Context gathered: 2026-03-18*
