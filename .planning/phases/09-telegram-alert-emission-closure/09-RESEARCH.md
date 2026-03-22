# Phase 09 Research: Telegram Alert Emission Closure

## Goal

Close the remaining milestone Telegram gap by adding one shipped runtime path that takes a qualifying setup, emits the Telegram alert, and makes that same emitted alert resolvable through the served callback flow.

This phase is not primarily about new Telegram callback features. Those seams already exist. The missing work is the producer/orchestrator path that connects scanner/runtime output to:

1. alert projection
2. delivery dedupe/state handling
3. Telegram send attempt
4. callback registry registration
5. end-to-end operator approval/adjustment evidence

## Current Truth

- The milestone audit already identifies the exact gap: `FLOW-01` is unsatisfied and `FLOW-02` / `FLOW-03` remain partial because callbacks are proven only after tests pre-register alert state rather than after live alert emission.
- `TelegramRuntimeDeliveryService` is implemented and records delivery attempts, but it only sends a prebuilt message through a transport seam. It does not own alert projection, registry writes, or scanner/runtime integration.
- `TelegramActionRegistry` is implemented and is the source of truth for callback resolution, stale-state checks, idempotency, and pending trade override sessions.
- `TelegramCallbackHandler`, `TelegramRoutes`, and the ASGI app boundary are implemented and tested.
- No production caller currently connects qualifying setup generation to `render_pre_entry_alert(...)`, `TelegramRuntimeDeliveryService.deliver(...)`, and `TelegramActionRegistry.register_alert(...)` in one runtime flow.

## File-Level Findings

- `backend/app/alerts/telegram_runtime.py`
  - Provides `TelegramDeliveryRequest` and `TelegramRuntimeDeliveryService.deliver(...)`.
  - Good transport boundary and retry accounting.
  - Not an orchestrator.
- `backend/app/alerts/action_resolution.py`
  - `TelegramActionRegistry.register_alert(...)` stores callback-resolvable alert state.
  - Registry semantics already support stale alert detection by symbol recency.
- `backend/app/alerts/delivery_state.py`
  - Encodes sparse Telegram emission rules: first surface, watch-to-actionable, duplicate suppression, and blocked/rejected suppression for unseen symbols.
  - This should stay the authority for emission dedupe.
- `backend/app/api/telegram_callbacks.py`
  - Accepts webhook callbacks and message replies through the served runtime boundary.
  - Already routes into `TelegramActionExecutor`.
- `backend/app/main.py`
  - Wires the served Telegram webhook surface only.
  - Does not compose any outbound alert producer/runtime service.
- `backend/tests/operator_workflow/test_telegram_runtime_delivery.py`
  - Proves delivery/retry/health behavior only.
- `backend/tests/operator_workflow/test_telegram_callback_routes.py`
  - Proves approve/reject/adjust flows only after direct `registry.register_alert(alert)` setup.
- `backend/tests/operator_workflow/test_telegram_webhook_serving.py`
  - Proves the ASGI webhook path, but still starts from pre-registered alerts.
- `backend/tests/operator_workflow/test_delivery_state.py`
  - Proves the desired alert emission policy but only as an isolated state machine.

## Standard Stack

- Keep the existing in-process Python architecture.
- Reuse `StrategyProjection`, `TradeProposal`, `PreEntryAlert`, `TelegramDeliveryState`, `render_pre_entry_alert`, `TelegramRuntimeDeliveryService`, `TelegramActionRegistry`, and `LifecycleLog`.
- Keep Telegram callback handling on the existing `POST /telegram/webhook` path.
- Prefer dependency-injected protocol seams over introducing external queues, background workers, or persistence in this phase.

## Architecture Patterns

- Add a single application service for outbound qualifying-alert emission.
  - Responsibility: accept a qualifying setup input, build the `PreEntryAlert`, consult `TelegramDeliveryState`, render the message, send it, record the outcome, and register callback state only when the delivery result is successful.
- Keep callback registration success-coupled to emission.
  - Registering before send recreates the current milestone ambiguity.
  - Registering after failed send creates honest behavior: callbacks are only resolvable for alerts that were actually emitted.
- Keep delivery policy separate from transport.
  - `TelegramDeliveryState` decides whether a symbol/state transition should send.
  - `TelegramRuntimeDeliveryService` performs the actual send and retry logic.
- Keep callback execution separate from emission.
  - `TelegramActionExecutor` should continue to consume registry state and should not absorb producer concerns.

## Recommended Service Shape

Create one runtime-facing service, conceptually similar to:

- `QualifyingAlertEmitter` or `TelegramAlertEmissionService`

Inputs:

- strategy projection
- proposal
- rank
- entry eligibility
- operator chat id
- observed/surfaced timestamp

Owned steps:

1. Build the `PreEntryAlert`.
2. Ask `TelegramDeliveryState.handle(alert)` whether this state should send.
3. If suppressed, return a structured no-op result.
4. Render the alert with `render_pre_entry_alert(alert)`.
5. Send via `TelegramRuntimeDeliveryService.deliver(...)`.
6. Record pre-entry lifecycle evidence only for the emitted alert path the phase wants to prove.
7. Register the alert in `TelegramActionRegistry` only after successful delivery.
8. Return a result object containing:
   - alert
   - delivery decision
   - delivery outcome
   - whether registry registration occurred

This service should be composed at an app/runtime boundary, not hidden in tests.

## What To Decide Before Planning

- What is the exact upstream input contract?
  - Best fit is likely a trigger-ready qualifying setup represented as `StrategyProjection + TradeProposal + rank + EntryEligibility`.
- Where does operator `chat_id` come from?
  - The existing delivery service requires it.
  - If no runtime config object already owns it, the phase needs a small runtime config seam.
- Should watch alerts be included in Phase 09?
  - The milestone gap is specifically about qualifying setup emission and operator entry continuity.
  - The minimum milestone closure path is actionable trigger-ready alerts.
  - Watch-alert support is already modeled in `TelegramDeliveryState` and may be included if cheap, but should not dilute the end-to-end proof target.
- When should lifecycle `PRE_ENTRY_ALERT` be recorded?
  - To match milestone wording, record it on the same emitted path that feeds callbacks.
  - Avoid recording alerts that were suppressed or failed delivery as if they had reached Telegram.

## Don't Hand-Roll

- Do not invent a second callback state store. Reuse `TelegramActionRegistry`.
- Do not duplicate the state-transition policy already encoded in `TelegramDeliveryState`.
- Do not move callback business logic into the webhook layer.
- Do not introduce async job infrastructure or persistence unless a real blocker appears. Nothing in the current codebase suggests this phase needs it.
- Do not “solve” the milestone by adding more tests that manually call `registry.register_alert(...)`.

## Common Pitfalls

- Registering alerts before confirmed send.
  - This would let callbacks resolve against alerts that never left the system.
- Treating a send attempt as equivalent to an emitted alert.
  - The audit gap is specifically about live emission continuity.
- Recording pre-entry audit evidence on suppressed states.
  - Suppressed blocked/rejected states for unseen symbols should remain suppressed.
- Over-expanding scope into a general scanner runtime.
  - Phase 09 needs one composable outbound producer path, not a full scanner daemon redesign.
- Re-testing seams instead of proving continuity.
  - Existing tests already cover delivery, callback execution, and webhook serving separately.

## Code Examples

- Emission policy reference: `backend/app/alerts/delivery_state.py`
- Callback registry reference: `backend/app/alerts/action_resolution.py`
- Runtime send reference: `backend/app/alerts/telegram_runtime.py`
- Renderer reference: `backend/app/alerts/telegram_renderer.py`
- Callback/webhook runtime reference: `backend/app/api/telegram_callbacks.py`, `backend/app/api/telegram_routes.py`, `backend/app/main.py`
- Current missing-E2E evidence examples: `backend/tests/operator_workflow/test_telegram_callback_routes.py`, `backend/tests/operator_workflow/test_telegram_webhook_serving.py`

## Validation Architecture

Plan validation around one shared fixture/service graph that uses the real emission service, real `TelegramDeliveryState`, real `TelegramActionRegistry`, real `TelegramActionExecutor`, and a fake transport.

Required test layers:

1. Producer-path integration test
   - Start from qualifying setup input.
   - Assert: alert is projected, dedupe policy is applied, message is rendered, send occurs, lifecycle alert evidence is recorded, and registry state is created from that same path.
2. Callback continuity test
   - First emit the alert through the producer path.
   - Then approve through `TelegramCallbackHandler` or `TelegramRoutes`.
   - Assert: approval opens a trade and uses the emitted alert id, not hand-injected state.
3. Adjustment continuity test
   - First emit through the producer path.
   - Then run `entry:ad:*` plus reply-message flow.
   - Assert: adjusted approval produces `ENTRY_DECISION` and `TRADE_OPENED` from emitted alert state.
4. ASGI boundary test
   - Emit through the producer path.
   - Send webhook payloads through `create_app()`.
   - Assert: served runtime closes the loop without direct registry setup in the test body.
5. Negative-path test
   - Failed send must not register callback state.
   - Duplicate/suppressed alert state must not create new callback-resolvable records.

Evidence standard for milestone closure:

- At least one end-to-end approval test and one end-to-end adjusted-approval test must begin with producer emission, not `registry.register_alert(...)`.
- Existing seam tests should remain, but they are supporting evidence only.

## Planning Implications

- This phase should likely break into:
  1. producer/orchestrator service
  2. runtime composition/wiring
  3. end-to-end validation replacement for pre-registration-based evidence
- Keep scope tight around `FLOW-01`, `FLOW-02`, and `FLOW-03`.
- Do not let Phase 09 drift into dashboard composition, persistence, or generalized runtime scheduling work.

## Constraints Discovered

- There is no local `CLAUDE.md`, `.claude/skills`, or `.agents/skills` instruction source adding extra project-specific constraints for this phase.
- `ROADMAP.md` and `REQUIREMENTS.md` already place `FLOW-01`, `FLOW-02`, and `FLOW-03` on Phase 09, so the plan should explicitly target milestone audit closure rather than generic cleanup.
- The existing callback and webhook tests currently prove the wrong starting point for milestone closure because they manually seed registry state.
