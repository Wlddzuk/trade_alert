# Phase 6 Research: Telegram Runtime Delivery and Callback Wiring

**Date:** 2026-03-18
**Phase:** 06
**Scope:** FLOW-01, FLOW-02, FLOW-03, FLOW-05

## Research Goal

Answer what the planner needs to know to turn the existing Telegram workflow models into a live runtime path for outbound alert delivery, inbound operator callbacks, and open-trade override actions.

## What Already Exists

### Domain and rendering logic are already in place

- `backend/app/alerts/models.py` already defines:
  - `PreEntryAlert`
  - `OpenTradeSnapshot`
  - stable `alert_id` / `trade_id`
  - Telegram callback payload limits through `TelegramButton`
- `backend/app/alerts/telegram_renderer.py` already renders:
  - pre-entry alerts with `Approve`, `Adjust`, `Reject`
  - open-trade messages with `Close`, `Adjust Stop`, `Adjust Target`
- `backend/app/alerts/approval_workflow.py` already converts operator intent into normalized domain actions:
  - `approve_with_defaults`
  - `approve_with_adjustments`
  - `reject_entry`
  - `close_trade`
  - `adjust_trade_stop`
  - `adjust_trade_target`

### Broker and audit sinks already exist

- `backend/app/paper/broker.py` already accepts normalized decisions and commands.
- `backend/app/audit/lifecycle_log.py` is already the append-only place to record:
  - pre-entry alert surfaces
  - entry decisions
  - open-trade commands
  - trade opens and closes

### Ops reporting primitives already exist

- `backend/app/ops/alert_delivery_health.py` already models delivery attempts, failure streaks, and recovery summaries.
- `backend/app/ops/incident_log.py` already converts delivery failures into incident records for operator review.
- Phase 5 already established that Telegram should stay sparse and high-signal during degrade/recovery.

### Test infrastructure already exists

- `backend/pyproject.toml` configures `pytest`.
- Existing tests under `backend/tests/operator_workflow/`, `backend/tests/paper_broker/`, and `backend/tests/ops_dashboard/` cover the pure-domain seams this phase should build on.

## Current Gaps

### No live transport boundary

There is no production adapter that takes a rendered Telegram message and attempts a real send while recording success/failure attempts.

### No inbound callback path

There is no route, webhook handler, or callback parser that turns Telegram callback payloads into:
- entry decisions
- guided adjustment session state
- open-trade commands

### No runtime conversation state

The new context requires guided adjustments, explicit cancel, timeout, idempotent repeats, and stale-message handling. None of that state exists yet.

### No real application surface

`backend/app/main.py` exposes a plain `BuySignalApp` object with dashboard route helpers only. It is not a served ASGI/HTTP application. Phase 6 therefore needs at least a minimal live operator-control surface, even if Phase 7 remains responsible for the broader served dashboard runtime.

## Planning Implications

### Phase 6 should be split around three seams

#### 1. Outbound Telegram delivery adapter

Planner should create a plan that introduces a transport-facing component responsible for:
- taking `RenderedTelegramMessage`
- sending it to Telegram
- recording `AlertDeliveryAttempt`
- retrying briefly on failure
- surfacing failure data to ops reporting

This should stay separate from alert projection/rendering. The renderer already exists; Phase 6 only needs runtime delivery.

#### 2. Callback parsing and action routing

Planner should create a plan that introduces a runtime boundary for Telegram callbacks and routes them into existing domain actions.

This layer needs to:
- authenticate or validate Telegram-originated webhook/callback requests
- decode callback payloads from current button shapes such as `entry:ap:{alert_id}` and `trade:st:{trade_id}`
- enforce newest-state-only semantics
- detect stale, duplicate, and superseded actions
- emit operator-readable responses

This layer should not embed paper-broker logic directly. It should translate transport events into the existing approval and command primitives.

#### 3. Guided adjustment session flow

Planner should create a plan for the conversational state required by the approved Phase 6 context:
- guided stop/target editing
- allow one-sided changes
- explicit cancel
- timeout expiry
- final confirmation before approval

This is the main net-new product logic in the phase. It needs its own storage/state model and should not be buried inside route code.

## Recommended Runtime Shape

### Keep transport-specific code behind a Telegram adapter boundary

Suggested separation:

- `alerts/telegram_renderer.py`
  - keep as pure rendering
- new Telegram runtime adapter module
  - perform sends
  - map Telegram transport failures into `AlertDeliveryAttempt`
  - optionally expose thin message-edit support for stale annotation
- new callback parsing/dispatch module
  - parse Telegram callback payloads and chat replies
  - resolve current alert/trade/session state
  - call existing workflow primitives

This preserves the existing clean separation between domain models and runtime transport.

### Introduce a minimal operator-control API surface, not a full dashboard server

Phase 6 should add only the smallest live application surface needed for Telegram:
- webhook endpoint(s) for Telegram updates
- runtime wiring to the callback dispatcher
- health-safe response handling

It should not pull Phase 7 dashboard serving work into this phase. The planner should keep dashboard route registration secondary unless required by shared app bootstrapping.

### Add a durable action-resolution seam

Because callback payloads only contain short IDs, runtime code will need a resolver that can answer:
- what is the current state for this `alert_id` or `trade_id`?
- is this action still valid?
- what current-state summary should be shown if it is stale or duplicate?

The planner should not rely on raw chat history for this. It should rely on current domain state plus lifecycle/audit-backed identifiers.

## Risks the Planner Must Account For

### 1. Callback payload size and state lookup

Telegram button payloads are already constrained to 64 bytes in `TelegramButton`. The planner should not expand payload format materially. Runtime should instead keep callback payloads compact and resolve context server-side from `alert_id` / `trade_id`.

### 2. Phase-boundary drift into dashboard serving

Because `main.py` is not a real app yet, the planner may be tempted to solve dashboard serving here too. That would blur Phase 6 and Phase 7. Phase 6 should add only the live boundary needed for Telegram actions.

### 3. Conversation-state complexity

Guided adjustments can easily sprawl into a general chat-bot framework. The context explicitly limits this:
- bounded adjustment sessions only
- no long-lived command bot
- no broad Telegram administration feature set

Planner should keep the session model narrow and expiration-driven.

### 4. Stale and duplicate actions

The repo currently models delivery-state history at the symbol/state level, but not callback validity across superseded alerts and trade messages. Planner must introduce explicit idempotency and stale-action checks or this phase will fail the audit gap in practice.

### 5. Operational visibility coupling

If send attempts are not recorded uniformly, Phase 5 ops surfaces will continue to show theoretical alert-delivery health instead of live runtime health. Planner should ensure delivery recording is first-class, not an afterthought.

## Recommended Plan Shape

The phase should likely produce 3 plans:

### Plan 06-01: Runtime Telegram delivery adapter

Focus:
- introduce outbound Telegram transport abstraction
- add bounded retry behavior
- record delivery attempts and failure outcomes
- connect rendered messages to runtime delivery

Primary files likely touched:
- new Telegram runtime adapter module(s)
- `backend/app/ops/alert_delivery_health.py` integration points
- tests for successful sends, retries, and failure reporting

### Plan 06-02: Callback route and action dispatch

Focus:
- add minimal live API/webhook entrypoint
- parse and validate callback payloads
- map callbacks into existing entry/trade command primitives
- enforce newest-state-only, stale, and duplicate handling

Primary files likely touched:
- `backend/app/main.py`
- new `backend/app/api/telegram_*.py` route/handler modules
- runtime dispatch/resolution modules
- tests for webhook request handling and stale/duplicate responses

### Plan 06-03: Guided adjustment sessions and operator feedback

Focus:
- implement bounded conversational state for alert adjustments
- support one-sided stop/target changes
- explicit cancel and timeout
- final confirmation
- operator-readable business-state and degradation responses

Primary files likely touched:
- new session-state modules under `alerts/` or `api/`
- callback/reply dispatch layer
- renderer additions for confirmation/stale-state annotations
- tests for guided adjustment happy path and expiration/cancel behavior

## Verification Strategy

### What should remain automated

Most of this phase is testable with `pytest` by exercising:
- transport adapter behavior with fake client(s)
- webhook/callback route behavior
- callback parsing and stale/duplicate rules
- guided adjustment session transitions
- broker integration from normalized command output
- ops-side delivery failure logging and recovery summaries

### What should be validated at route level

The current tests are mostly pure-domain. Phase 6 needs higher-level tests that prove:
- a webhook update enters the app boundary
- callback payloads become the correct domain action
- stale or repeated actions return the intended operator response
- successful/failed sends update delivery health state

### What should stay manual or UAT-backed

Only a small manual/UAT slice should remain:
- confirm real Telegram formatting/readability once a live token/chat exists
- confirm webhook wiring expectations in the deployment environment

The core behavior should still be automated with fake transport fixtures.

## Validation Architecture

Nyquist validation strategy should be created for this phase.

### Recommended framework and commands

- **Framework:** `pytest`
- **Config file:** `backend/pyproject.toml`
- **Quick run command:** `cd backend && uv run pytest tests/operator_workflow tests/ops_dashboard -q`
- **Full suite command:** `cd backend && uv run pytest`
- **Estimated runtime:** quick run should remain under ~20 seconds; full suite under ~60 seconds for this codebase size

### Validation focus by plan

- **06-01 runtime delivery**
  - adapter send success
  - bounded retry then failure record
  - ops delivery snapshot/recovery updates
- **06-02 callback routing**
  - valid callback to normalized action
  - stale/superseded callback rejection
  - duplicate callback idempotent acknowledgement
  - minimal app/webhook boundary coverage
- **06-03 guided adjustments**
  - sequential stop/target collection
  - one-sided edits
  - explicit cancel
  - timeout expiry
  - final confirmation before approval

### Wave 0 expectations

Planner should expect to add new test modules before or alongside implementation, likely under:
- `backend/tests/operator_workflow/`
- `backend/tests/ops_dashboard/`
- route-level tests for the new Telegram API surface

There is no sign the repo needs a new framework, only additional fixtures and test files.

## Key Constraint Summary For Planner

- Do not redesign Phase 4 alert semantics.
- Do not expand into dashboard-led controls.
- Do not turn this into a general Telegram bot framework.
- Do add a minimal live runtime boundary for Telegram callbacks.
- Do preserve compact callback payloads and resolve state server-side.
- Do make failure visibility and idempotency explicit because those are part of the gap closure, not polish.
