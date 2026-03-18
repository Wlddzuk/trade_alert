# Phase 6: Telegram Runtime Delivery and Callback Wiring - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the live operator-workflow gap by wiring Telegram alert delivery, callback handling, and override actions into the application runtime.

This phase turns the already-defined Phase 4 Telegram workflow into a live runtime surface. It does not redesign alert semantics, add dashboard-led control, or expand beyond Telegram delivery, operator decisions, and open-trade override handling.

</domain>

<decisions>
## Implementation Decisions

### Adjustment conversation flow
- Actionable alert adjustments should use a guided chat flow in Telegram rather than slash commands or one-shot freeform input.
- After the operator taps `Adjust`, the bot should collect revised values in sequence inside the chat.
- The operator may change only one side of the proposal and keep the other proposed value unchanged.
- After revised values are collected, the bot should present a final confirmation step before the paper trade is opened.
- Adjustment flows should support explicit cancel and also expire automatically after a short timeout if left unfinished.

### Stale and repeated action handling
- Telegram actions should follow a strict newest-state-only rule.
- Only the current actionable alert or current open-trade state should accept actions; older related messages become invalid once superseded.
- When an outdated button is tapped, the bot should explain that the action is no longer valid and show the current relevant alert or trade state.
- When possible, superseded Telegram messages should be edited or annotated to show that they are stale rather than left looking actionable.
- Repeated actions that already succeeded should be handled idempotently with an acknowledgement plus the resulting current state.

### Operator-facing runtime failures
- If a Telegram action reaches the backend but cannot be applied, the bot should return a clear, operator-readable reason with retry guidance.
- Business-state refusals should be specific, such as cooldown active, trade already closed, or alert superseded, rather than generic unavailable messaging.
- If Telegram workflow actions are impaired by degraded or unavailable system state, Telegram should send one high-signal notice when the issue begins and one recovery notice when it ends.
- Outbound Telegram sends should retry automatically for a short bounded window before the system records and surfaces an operational failure incident.

### Already-fixed inputs Phase 6 must honor
- Telegram remains the primary operator surface in v1.
- Watch alerts surface first for valid non-trigger-ready setups, then fresh actionable alerts when trigger-ready.
- Entry remains human-approved with both fast default approval and a separate adjustment path.
- Open-trade override remains limited to close, stop adjustment, and target adjustment.
- Telegram trade messaging remains material-events-only and the dashboard stays secondary and read-only.

### Claude's Discretion
- Exact copy, prompts, and button labels for guided adjustment and stale-state responses.
- Exact timeout duration for unfinished adjustment conversations.
- Exact format used to collect adjusted stop/target inputs, as long as it stays guided and operator-readable.
- Exact retry count and retry backoff for outbound Telegram delivery failures, as long as retries stay brief and bounded.

</decisions>

<specifics>
## Specific Ideas

- The live Telegram runtime should feel strict but not silent:
  - old buttons should fail clearly
  - repeated taps should be safe and acknowledged
  - current state should stay obvious after refusals
- Preserve the fast operator loop from Phase 4:
  - one-tap default approval remains available
  - adjustments are conversational only when needed
  - trade controls remain narrow and explicit
- Keep historical chat context visible where possible by marking superseded messages stale instead of deleting them.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/alerts/telegram_renderer.py`
  - Already renders pre-entry alerts, trade-opened messages, trade-adjusted messages, and trade-closed messages with callback payloads for approve, adjust, reject, close, adjust stop, and adjust target.
- `backend/app/alerts/approval_workflow.py`
  - Already defines normalized entry-decision and open-trade-command models for default approval, adjusted approval, reject, close, adjust stop, and adjust target actions.
- `backend/app/alerts/models.py`
  - Already defines stable alert and trade identifiers plus callback payload size constraints that the runtime adapter should preserve.
- `backend/app/alerts/delivery_state.py`
  - Already models surfaced-symbol history and duplicate-state suppression; this phase can extend it into runtime delivery semantics instead of replacing it.
- `backend/app/audit/lifecycle_log.py`
  - Already records pre-entry alerts, entry decisions, and trade commands, which gives the runtime path an existing audit sink.
- `backend/app/ops/alert_delivery_health.py` and `backend/app/ops/overview_service.py`
  - Already provide operational reporting patterns for alert-delivery failures and recovery incidents.

### Established Patterns
- Operator-facing behavior is built on normalized internal models, not raw vendor or transport payloads.
- Telegram is the primary control surface and should remain concise, explicit, and material-events-only.
- UTC-safe identifiers and append-only lifecycle logging are already established and should remain intact through runtime wiring.
- The dashboard remains observational, so callback and operator-control behavior belongs in Telegram rather than being split across surfaces.

### Integration Points
- `backend/app/main.py`
  - Currently exposes only a thin app object with dashboard routes; Phase 6 needs a real runtime boundary that can host Telegram delivery and callback handling.
- `backend/app/api/`
  - Currently contains dashboard-only route helpers, so Telegram webhook or callback entrypoints will need to become the first live operator-control API surface.
- `backend/app/paper/broker.py`
  - Existing broker and trade-command seams provide the runtime sink for approved entries and open-trade overrides once Telegram decisions are decoded.

</code_context>

<deferred>
## Deferred Ideas

- Dashboard-led approvals or any second control plane remain out of scope.
- Rich command-based Telegram administration beyond the approval and override loop remains out of scope for this phase.
- Long-lived conversational workflows beyond bounded adjustment collection are deferred.
- Any live broker or venue-specific execution behavior remains outside v1 and outside this phase.

</deferred>

---

*Phase: 06-telegram-runtime-delivery-and-callback-wiring*
*Context gathered: 2026-03-18*
