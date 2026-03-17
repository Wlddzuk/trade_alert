# Phase 5: Monitoring, Audit, and Review Surface - Research

**Researched:** 2026-03-17
**Domain:** degraded-state visibility, operational monitoring, immutable audit review, paper P&L summaries, and a secondary read-only dashboard for a Telegram-led US-equity paper-trading system
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 5 must keep the dashboard secondary, read-only, and clearly separate from the Telegram approval workflow.
- The dashboard must be status-first and summary-first.
- Degraded and recovering trust states must stay prominent through a persistent dashboard warning surface.
- Stale scanner rows may remain visible during degraded periods, but only as clearly untrusted context.
- Outside the runtime window, the status surface should remain visible in a neutral offline/session-closed state rather than degraded.
- Telegram trust messaging must remain sparse:
  - one degrade alert
  - one recovery alert
  - no reminder spam while degraded
- Completed paper trades must be grouped by trading day by default.
- Trade review must be summary-first with drill-down.
- Raw lifecycle events should remain secondary to the human-readable review.
- Ops overview must prioritize:
  - provider freshness ages
  - scanner-loop health
  - alert-delivery health
- Runtime and scanner errors should surface as recent critical issues first, with deeper history in a separate logs section.
- Alert-delivery failures should show both summary health and recent failed attempts when relevant.
- Paper P&L should be:
  - today-first
  - realized-first
  - paired with trade count and win rate
  - backed by simple day-by-day history rather than chart-first analytics

### Claude's Discretion
- Exact banner copy, status labels, iconography, and color treatment.
- Exact section names and panel layout, as long as the read-only, status-first posture holds.
- Exact recent-history window for resolved incidents.
- Exact trade-review row layout and P&L formatting details.
- Exact technical choice for the thin dashboard surface, provided it stays backend-dominant and secondary.

### Deferred Ideas (OUT OF SCOPE)
- Dashboard-led trade approvals or any second control plane
- Advanced analytics beyond day-by-day paper P&L summaries
- Chart-first or rich visualization-heavy review surfaces
- Live execution controls or venue-specific management UI

</user_constraints>

<research_summary>
## Summary

Phase 5 should not be planned as “just add a dashboard page.” It needs three distinct layers:

1. Operational read models over trust, freshness, scanner-loop health, alert delivery, and incident history
2. Audit review and paper-P&L read models over the immutable Phase 4 lifecycle stream
3. A thin, explicitly read-only dashboard surface that composes those backend summaries without becoming a second workflow surface

Five planning realities matter:

1. The backend already has the hard parts of truth and audit.
   `SystemTrustMonitor`, `SystemEvent`, `LifecycleLog`, and `TradeReview` already exist. Phase 5 should consume and shape those outputs rather than recomputing trust or trade history from scratch.

2. There is still no web surface in the codebase.
   The repo has no existing API/router/main entrypoint and no dashboard frontend. Because the dashboard is secondary and read-only, the pragmatic Phase 5 move is a thin backend-served dashboard/read-model layer rather than treating a separate frontend app as a hidden prerequisite.

3. Current status and recent incident history are different surfaces.
   The operator needs to know both what the system is doing now and what just went wrong or recovered recently. These should be modeled separately so the overview stays concise while still preserving operator confidence.

4. Review and P&L must derive from immutable lifecycle events.
   Phase 4 already chose append-only lifecycle storage. Phase 5 should build grouped review, result summaries, and day-by-day P&L off that stream rather than creating a second mutable source of truth.

5. The dashboard must remain obviously observational.
   Read-only labeling, omitted trade controls, and status-first layout are product constraints, not styling details.

**Primary recommendation:** Keep Phase 5 split into three plans across two waves:
- `05-01` ops read models, alert-delivery health, and incident history
- `05-02` trade review grouping and paper-P&L summaries
- `05-03` thin backend-served read-only dashboard over the Phase 5 read models

</research_summary>

<architecture_patterns>
## Phase Architecture Guidance

### 1. Consume existing trust outputs rather than recomputing health

Phase 1 already established:
- `SystemTrustMonitor`
- `ProviderFreshnessStatus`
- trust transitions and system events

Planning implication:
- Phase 5 should build overview/status read models from `SystemTrustSnapshot` and `SystemEvent`
- the dashboard should not infer degraded/recovering/offline state ad hoc from raw provider timestamps
- stale-row visibility should remain a presentation concern on top of trust state, not a second trust engine

### 2. Separate current overview state from recent incidents and deeper logs

The user chose:
- trust state first
- recent critical issues first
- recently resolved incidents still visible after recovery

Planning implication:
- model current overview state separately from incident history
- model incident severity/recovery state explicitly enough for “recent critical” and “recently resolved” views
- keep deeper raw logs behind a separate read-only logs section instead of on the landing overview

### 3. Build review and P&L as read models over the lifecycle stream

Phase 4 already established:
- append-only lifecycle events
- derived `TradeReview`

Planning implication:
- extend audit read models rather than inventing dashboard-only trade summaries
- group completed trades by trading day from immutable events
- derive realized-first today/cumulative/day-history P&L from closed-trade lifecycle outcomes
- keep raw lifecycle events available as drill-down detail instead of the primary review surface

### 4. Prefer a thin backend-served read-only dashboard in this phase

Current repo reality:
- Python backend exists
- no API surface exists
- no frontend app exists

Planning implication:
- Phase 5 should introduce the minimal dashboard-serving surface needed to satisfy FLOW-06
- keep the backend dominant and the dashboard thin
- avoid planning a heavyweight separate frontend platform as if it were already present

This does not rule out a richer frontend later. It simply keeps the last v1 phase aligned with the current codebase and the “secondary dashboard” product decision.

### 5. Make read-only posture explicit in both data and presentation

The user chose:
- explicit read-only labeling
- no trade-action controls

Planning implication:
- dashboard view models should not expose action affordances
- tests should explicitly verify the absence of control actions and the presence of read-only cues
- the dashboard should compose summaries and drill-down information only

### 6. Keep dashboard sections summary-first

The user chose:
- overview first
- compact panels first
- summary review first
- day-by-day P&L history rather than analytics-heavy visuals

Planning implication:
- plan for stable summary models before renderers
- make drill-down an extension of summary read models rather than a separate parallel data shape
- avoid chart-first or raw-log-first planning

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trust status in dashboard | ad hoc freshness or banner logic in UI code | read models over `SystemTrustSnapshot` and `SystemEvent` | Keeps trust semantics identical across Telegram and dashboard |
| Trade review | mutable current-trade reconstruction | immutable lifecycle-derived review models | Preserves Phase 4 audit contract |
| P&L summaries | hand-maintained counters separate from lifecycle | derived realized summaries from closed-trade events | Avoids drift between review and performance views |
| Logs surface | dump of raw events on landing page | current overview + incident history + deeper logs section | Keeps the overview readable |
| Dashboard scope | latent action buttons or future-control placeholders | explicit read-only label and omitted controls | Avoids creating a second control plane by accident |

**Key insight:** Phase 5 should add read models and a thin read-only surface over the Phase 1-4 backend contracts, not a parallel workflow stack.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Recomputing degraded state in the dashboard layer
**What goes wrong:** Dashboard status diverges from Telegram trust behavior.
**Why it happens:** UI code often re-derives health from raw timestamps instead of using a stable backend truth.
**How to avoid:** Shape explicit read models from existing trust snapshots and transition events.
**Warning signs:** Multiple places independently define “degraded,” “recovering,” or “offline.”

### Pitfall 2: Mixing current status and historical incidents together
**What goes wrong:** The overview becomes noisy and hard to scan.
**Why it happens:** Everything operational gets pushed into one generic “logs” model.
**How to avoid:** Separate current system summary from recent incident history and deeper logs.
**Warning signs:** The landing view starts to look like a raw terminal dump.

### Pitfall 3: Letting trade review depend on mutable trade state
**What goes wrong:** Historical review becomes incomplete or inconsistent after state changes.
**Why it happens:** The lifecycle stream already exists, but it feels easier to query current trade objects.
**How to avoid:** Derive grouped review and P&L summaries from immutable lifecycle data only.
**Warning signs:** Review code reads live broker state instead of lifecycle events.

### Pitfall 4: Overbuilding the dashboard as a second product
**What goes wrong:** The final phase balloons into a frontend platform project.
**Why it happens:** “Dashboard” gets interpreted as a rich app instead of a secondary read-only surface.
**How to avoid:** Keep the surface backend-dominant, sectioned, summary-first, and explicitly read-only.
**Warning signs:** Plans start introducing action controls, rich workflows, or chart-heavy analytics as core scope.

### Pitfall 5: Treating alert-delivery health as a hidden backend concern
**What goes wrong:** The operator sees degraded trust and scanner issues, but not whether Telegram delivery itself is failing.
**Why it happens:** Alert delivery is often considered transport plumbing instead of operator trust data.
**How to avoid:** Model delivery health and recent failures explicitly in the ops read layer.
**Warning signs:** “Healthy” dashboard states can coexist with undelivered operator alerts.

</common_pitfalls>

## Validation Architecture

- Keep Phase 5 fully automated under `pytest`.
- Add three test groups aligned to the plans:
  - `tests/ops_dashboard/` for trust overview, alert-delivery health, and incident history
  - `tests/audit_review/` for grouped trade review and paper-P&L summaries
  - `tests/dashboard/` for the read-only dashboard surface and section composition
- Validate the read-only posture directly:
  - no action controls in the dashboard surface
  - degraded/recovering/offline states render distinctly
  - review grouping and P&L summaries match immutable lifecycle inputs
- Keep full-suite regression as the phase-level backstop since Phase 5 consumes outputs from Phases 1-4.

---
*Research for: Monitoring, Audit, and Review Surface*
*Researched: 2026-03-17*
