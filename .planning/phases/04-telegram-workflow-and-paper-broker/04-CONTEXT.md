# Phase 4: Telegram Workflow and Paper Broker - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the core operator loop for v1: Telegram-led alerts, human-approved paper entries, fixed-risk paper sizing, trade-quality rejection, rule-based paper exits, and full lifecycle logging.

This phase clarifies how the operator experiences alerts, approvals, blocked trades, paper fills, and exits. It does not expand dashboard scope beyond the already-decided secondary read-only role, and it does not add live execution or venue-specific order models.

</domain>

<decisions>
## Implementation Decisions

### Telegram alert progression
- Telegram remains the primary operator surface in v1.
- A setup may surface in Telegram twice as it progresses:
  - first as a watch-only alert when the setup is valid but not yet trigger-ready
  - later as a fresh actionable alert when the setup becomes trigger-ready
- A valid-but-not-trigger-ready setup must not be approval-capable.
- When a watched setup becomes trigger-ready, Telegram should send a new actionable alert rather than only editing the earlier watch message.

### Approval interaction
- Entry remains human-approved in v1.
- The fastest approval path should be one-tap approval using the proposed trade values from the alert.
- The operator must still have a separate adjust path before entry for:
  - stop
  - target
- Entry price should stay tied to the alert proposal in v1 rather than becoming operator-editable.
- The approval interaction should therefore support both:
  - fast default approval
  - explicit stop/target adjustment before paper-trade creation when needed

### Trade-quality rejection and blocked-entry behavior
- Phase 4 trade-quality gates remain in force before a paper trade can open, including the already-decided checks for:
  - spread
  - liquidity
  - stop distance
  - cutoff time
  - cooldown state
  - max open positions
- If a setup is rejected by these gates, Telegram should only send a rejection notice when that symbol has already been surfaced in Telegram.
- If a setup becomes trigger-ready while entry is blocked by rules such as max positions, cutoff time, or cooldown, Telegram should keep the symbol visible as a blocked non-actionable update rather than dropping it silently or queueing it for later replay.

### Paper-trade exit posture
- Once a paper trade is opened, exits should be system-managed by default.
- The default exit set for v1 should be protective plus responsive:
  - hard stop
  - target
  - early exit on weak follow-through or momentum failure
- When a pre-approved exit rule fires, the paper broker should close the trade automatically in v1 rather than waiting for manual confirmation.
- Operator override must remain available while the trade is open.
- Allowed open-trade override actions in v1 are:
  - close immediately
  - adjust stop
  - adjust target

### Telegram messaging during open trades
- Open-trade messaging in Telegram should stay material-events-only in v1.
- Material events include:
  - trade opened
  - operator adjustment applied
  - blocked or rejected status change relevant to an already-surfaced symbol
  - trade closed
  - final result summary
- Telegram should not emit a message for every internal rule evaluation or intermediate paper-broker state change.

### Already-fixed inputs that Phase 4 must honor
- Fixed risk per trade remains `1.0%` of paper account equity.
- Max daily loss remains `3.0%` of paper account equity.
- Max open positions remains `1` for MVP.
- Entry cutoff remains `15:30 ET`.
- Cooldowns remain:
  - `10 minutes` after any loss
  - `30 minutes` after `2` consecutive losses
- Every paper trade requires a stop.
- Default paper slippage remains configurable with `5 bps per side` as the initial default.
- Partial-fill simulation remains supported by the architecture but off by default in v1.

### Claude's Discretion
- Exact Telegram copy, button labels, and message formatting.
- Exact alert-expiry windows for watch and actionable alerts, provided the workflow still favors fast-moving setups and stale actions are prevented.
- Exact operational definitions for weak follow-through and momentum-failure exits, provided they stay inside the chosen protective-plus-responsive exit posture.
- Exact lifecycle state names used internally by the paper broker, provided they preserve the operator-facing behavior decided here.

</decisions>

<specifics>
## Specific Ideas

- Keep the Telegram loop fast and readable:
  - watch alert first for context
  - actionable alert only when trigger-ready
  - blocked or rejected updates only when the operator already has that symbol in view
- Preserve the scanner-first posture from earlier phases:
  - Telegram should consume the ranked strategy state rather than inventing new signal semantics
  - the paper broker should respect, not replace, Phase 3 setup and invalidation outputs
- Keep the open-trade workflow narrow in v1:
  - fast default approval path
  - optional stop/target adjustment path
  - automatic rule-based exits
  - operator override for close and level changes only

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/scanner/strategy_projection.py`
  - `StrategyProjection` already combines candidate row, `setup_valid`, score, stage tag, supporting reasons, and primary invalid reason into an operator-facing strategy record.
- `backend/app/scanner/strategy_tags.py`
  - Current stage tags already distinguish `building`, `trigger_ready`, and `invalidated`, which maps cleanly onto the decided watch-alert and actionable-alert progression.
- `backend/app/scanner/trigger_logic.py`
  - `TriggerEvaluation` already exposes whether the setup triggered, the trigger price, interval, and whether the lower-timeframe fallback was used.
- `backend/app/scanner/invalidation.py`
  - Existing invalidation reasons already capture stale catalyst, contradictory catalyst, lost context, halt, weak RVOL, and dead-move states that can feed blocked or responsive-exit behavior.
- `backend/app/scanner/feed_service.py`
  - Strategy-aware ordering already exists and should remain the source of ranked candidate priority for Telegram.
- `backend/app/ops/degraded_state.py` and `backend/app/ops/system_events.py`
  - The codebase already has a pattern for operator-visible system events and state transitions, which Phase 4 can reuse for Telegram status messaging instead of inventing a separate event style.

### Established Patterns
- Downstream logic consumes normalized internal models only; Phase 4 should not introduce raw vendor payload handling into alerting or paper-trade code.
- The feed remains symbol-centric and unified across premarket and the regular open.
- Strategy state is layered above candidate rows rather than mutating the row contract directly.
- Provider trust and degraded-state handling are already explicit and should continue to gate operator-facing actionability.

### Integration Points
- Phase 4 should consume ranked `StrategyProjection` outputs rather than raw `CandidateRow` instances.
- Approval-capable Telegram alerts should only emerge after the Phase 3 strategy state exists and the Phase 4 trade-quality gates allow entry.
- The paper broker should sit behind its own abstraction boundary so later venue-specific execution models can reuse the operator and risk workflow.
- Paper-trade lifecycle events should be shaped so Phase 5 can review them in the read-only dashboard and audit surfaces without retrofitting the event model later.

### Current Gaps
- There is not yet an alerting module, Telegram adapter, paper-broker state model, or trade-lifecycle persistence layer in the backend.
- Phase 4 planning should therefore define these pieces around the existing scanner and ops seams rather than refactoring the earlier phases.

</code_context>

<deferred>
## Deferred Ideas

- Dashboard-led approvals or any second control plane remain out of scope for this phase.
- Live execution behavior and venue-specific order models remain outside v1 and outside this phase.
- Queueing blocked setups for later replay is deferred; v1 should keep blocked symbols visible rather than building a resend queue.
- Rich per-tick or per-rule Telegram trade narration is deferred; v1 uses material-events-only trade messaging.

</deferred>

---

*Phase: 04-telegram-workflow-and-paper-broker*
*Context gathered: 2026-03-15*
