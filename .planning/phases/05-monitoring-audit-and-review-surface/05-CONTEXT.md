# Phase 5: Monitoring, Audit, and Review Surface - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the system trustworthy in use through degraded-state handling, audit review, and a read-only operator dashboard.

This phase clarifies how the operator sees trust state, health signals, logs, lifecycle review, and paper P&L. It does not expand the dashboard into a control surface, and it does not add new execution behavior beyond the completed Phase 4 workflow.

</domain>

<decisions>
## Implementation Decisions

### Degraded-state visibility and trust posture
- The dashboard must show a persistent top-level degraded/untrusted banner or status strip whenever trust is `degraded` or `recovering`.
- If the system becomes degraded because feeds are stale, scanner rows may remain visible in the read-only dashboard, but they must be clearly marked stale/untrusted.
- New actionable output remains blocked while degraded; keeping stale rows visible is for context only, not continuity of trust.
- Telegram should stay sparse:
  - one degrade alert when trust first degrades
  - one recovery alert when trust is restored
  - no periodic reminder spam while the system remains degraded
- Outside the runtime window, the same dashboard status surface should remain visible but move into a neutral offline/session-closed state rather than showing degraded.
- Recently resolved incidents should remain visible in a recent-history area after recovery rather than disappearing immediately.

### Dashboard landing and read-only posture
- The secondary dashboard remains read-only in v1.
- The default landing view should be system-status first, not trade-review first and not P&L first.
- The navigation shape should be:
  - one status-first overview
  - separate read-only sections for logs, trade review, and P&L
- The landing page should be summary-first:
  - compact status cards/panels first
  - deeper detail in lower sections or drill-down views
- The read-only nature should be explicit:
  - show a clear read-only label or badge
  - omit all trade-action controls
- The dashboard should not present itself like a second trading cockpit in v1.

### Trade-review presentation
- Completed paper trades should be grouped by trading day by default.
- Within each trading day, newest completed trades should appear first.
- The default review list should be summary-first with drill-down:
  - concise trade summary row/card first
  - deeper lifecycle/timeline view when opened
- Default trade summaries should show result plus operator path at a glance, including:
  - symbol
  - key times
  - entry and exit
  - realized P&L
  - exit reason
  - key operator path
- When the operator drills into a completed trade, the human-readable review should come first.
- Raw lifecycle events should remain available as a secondary detail panel rather than dominating the main review presentation.

### Ops and log visibility
- After overall trust state, the most prominent operational information on the overview should be:
  - provider freshness ages
  - scanner-loop health
  - alert-delivery health
- Runtime and scanner errors should appear as recent critical issues first, with deeper history in a separate read-only logs section.
- Alert-delivery failures should be surfaced in two ways:
  - summary delivery-health status
  - recent failed attempts when relevant
- The main overview should remain operator-readable rather than turning into a raw log console.
- Resolved incidents should remain visible in recent-history view after recovery so the operator can confirm what happened.

### Paper P&L summary posture
- The dashboard should emphasize today's paper P&L first.
- Cumulative-to-date paper P&L should remain visible as a secondary summary.
- Realized P&L should be primary.
- Open/unrealized exposure may appear as secondary context, but should not dominate the summary.
- The most useful companion metrics next to P&L are:
  - trade count
  - win rate
- Historical performance should use a simple day-by-day summary list in v1 rather than making a trend chart the main view.

### Claude's Discretion
- Exact banner copy, severity labels, iconography, and color treatment for trust states.
- Exact panel names and section labels, as long as the dashboard stays explicitly read-only and status-first.
- Exact lookback window for recent-history incidents on the overview.
- Exact trade-review row layout and day-group header style, as long as the chosen grouping and detail posture stay intact.
- Exact formatting of P&L, win rate, freshness ages, and timestamps, as long as UTC-safe internals remain preserved.

</decisions>

<specifics>
## Specific Ideas

- Treat trust state as the most important dashboard signal in v1.
- Keep the dashboard useful during degraded periods by showing context, not pretending the system is actionable.
- Favor summary-first views everywhere:
  - overview cards first
  - trade-review summaries first
  - recent critical issues first
  - day-by-day P&L summaries first
- Keep the dashboard obviously secondary to Telegram:
  - informative
  - reviewable
  - not interactive for trade control

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/ops/degraded_state.py`
  - `SystemTrustMonitor` already models `healthy`, `degraded`, and `recovering` trust states plus transition events.
- `backend/app/ops/system_events.py`
  - already exposes operator-visible degrade, recovering, and restored event types
- `backend/app/ops/health_models.py`
  - already carries provider freshness thresholds, freshness status, and full trust snapshots
- `backend/app/audit/lifecycle_log.py`
  - already provides append-only lifecycle-event recording for alerts, entry decisions, trade opens, trade commands, and trade closes
- `backend/app/audit/trade_review.py`
  - already derives operator-friendly trade reviews from the immutable event stream
- `backend/app/alerts/delivery_state.py`
  - already models surfaced-symbol history and sparse Telegram-delivery behavior that Phase 5 monitoring can report on
- `backend/app/runtime/session_window.py`
  - already exposes runtime phase and active/offline session semantics that can feed the dashboard status surface

### Established Patterns
- Internal state is UTC-safe and normalized before downstream use.
- Operator-facing logic is layered on top of normalized contracts rather than raw provider payloads.
- Telegram remains the primary workflow surface; the dashboard must stay observational.
- Lifecycle review should derive from immutable events, not from mutable broker state or reconstructed guesses.
- Trust is already treated as actionable/not-actionable state, not merely a cosmetic health metric.

### Integration Points
- Phase 5 should consume `SystemTrustSnapshot` and `SystemEvent` outputs rather than recomputing degraded logic in the dashboard layer.
- Phase 5 review surfaces should consume `LifecycleLog` and `TradeReview` outputs rather than rebuilding trade history from open-trade state.
- Phase 5 should expose alert-delivery health and recent failures using the existing operator-workflow and alerting seams from Phase 4.
- Runtime session state should feed the neutral offline/session-closed display choice already decided here.

### Current Gaps
- There is still no dashboard surface or read-only review UI in the codebase.
- There is no current aggregation layer that turns trust snapshots, recent incidents, alert-delivery issues, lifecycle reviews, and day-level P&L into one coherent dashboard view.
- There is no read-only logs surface yet for recent critical issues and recent resolved incidents.

</code_context>

<deferred>
## Deferred Ideas

- Dashboard-led trade approvals or any second operator control plane remain out of scope.
- Advanced performance analytics beyond simple day-by-day paper P&L summaries remain out of scope for this phase.
- Rich visual charting as the primary P&L review experience is deferred.
- Any new live-execution or broker-control UI remains out of scope.

</deferred>

---

*Phase: 05-monitoring-audit-and-review-surface*
*Context gathered: 2026-03-16*
