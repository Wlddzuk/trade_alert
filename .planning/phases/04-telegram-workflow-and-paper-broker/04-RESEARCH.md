# Phase 4: Telegram Workflow and Paper Broker - Research

**Researched:** 2026-03-15
**Domain:** Telegram-led operator workflow, paper broker behavior, trade-quality gates, and lifecycle recording for a scanner-first US-equity trading system
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 4 delivers the operator loop for v1 without expanding the dashboard beyond its read-only role.
- Telegram remains the primary operator surface in v1.
- A symbol may surface in Telegram twice:
  - watch-only when valid but not yet trigger-ready
  - a fresh actionable alert when it becomes trigger-ready
- Valid-but-not-trigger-ready setups are not approval-capable.
- Entry remains human-approved in v1.
- The fastest approval path is one-tap default approval using the alert proposal.
- The operator must also have a separate pre-entry adjust path for:
  - stop
  - target
- Entry price remains tied to the alert proposal in v1 and is not operator-editable.
- Trigger-ready setups blocked by max positions, cutoff time, or cooldown stay visible as blocked non-actionable updates rather than being dropped or queued.
- Rejection notices should only be sent in Telegram if that symbol was already surfaced there.
- Open paper trades use automatic protective-plus-responsive exits:
  - hard stop
  - target
  - early exit on weak follow-through or momentum failure
- Operator override during an open trade is limited to:
  - close immediately
  - adjust stop
  - adjust target
- Telegram trade messaging stays material-events-only:
  - trade opened
  - operator adjustment applied
  - blocked or rejected status change for an already-surfaced symbol
  - trade closed
  - final result summary
- Fixed risk per trade stays `1.0%` of paper account equity.
- Max daily loss stays `3.0%` of paper account equity.
- Max open positions stays `1`.
- Entry cutoff stays `15:30 ET`.
- Cooldowns stay:
  - `10 minutes` after any loss
  - `30 minutes` after `2` consecutive losses
- Every paper trade requires a stop.
- Default slippage stays configurable with `5 bps per side` as the initial default.
- Partial-fill simulation remains supported by architecture but off by default in v1.

### Claude's Discretion
- Exact Telegram copy and button labels.
- Exact alert-expiry windows for watch and actionable alerts.
- Exact operational definitions for weak follow-through and momentum-failure exits.
- Exact internal lifecycle state names for paper trades and operator approvals.

### Deferred Ideas (OUT OF SCOPE)
- Dashboard-led approvals or any second control plane.
- Live execution and venue-specific order models.
- Replay queues for blocked setups.
- Rich per-tick or per-rule Telegram narration.

</user_constraints>

<research_summary>
## Summary

Phase 4 should not be planned as “Telegram glued directly onto the scanner.” It needs four distinct layers that line up with the roadmap:

1. Telegram alerting and operator-decision handling
2. Paper-broker trade state and fill/exit behavior
3. Risk and eligibility gates reused by both alerting and entry
4. Immutable lifecycle events for downstream review

Four planning realities matter:

1. Phase 3 already produces the right operator-facing signal object.
   `StrategyProjection` contains score, validity, stage tag, and supporting reasons, so Phase 4 should consume it directly rather than rebuilding signal semantics from raw rows.

2. Alert transport and operator intent should be separated.
   Telegram message rendering and delivery are not the same concern as approval, rejection, or stop/target adjustment decisions. Planning should model operator intent independently so the workflow remains testable and later transport-agnostic.

3. Trade-quality gating must exist in two places, not one.
   The system should evaluate actionability before sending approval-capable alerts, and then re-check eligibility again immediately before opening the paper trade so stale state does not create invalid entries.

4. The paper broker should be event-driven and append-only from day one.
   Phase 5 depends on reconstructable lifecycle history, so Phase 4 should emit immutable events for signal surfacing, approvals, fills, adjustments, exits, and results rather than trying to recover those later from mutable trade state.

**Primary recommendation:** Keep the roadmap split as four plans in four waves:
- `04-01` Telegram message projection, delivery, and approval-intent handling
- `04-02` paper trade state, fill simulation, and exit handling
- `04-03` risk sizing, trade-quality gates, cutoff/max-position/cooldown enforcement
- `04-04` immutable lifecycle recording and downstream review-ready trade logs

</research_summary>

<architecture_patterns>
## Phase Architecture Guidance

### 1. Consume strategy projections directly

Phase 3 already established:
- `StrategyProjection` as the ranked operator-facing strategy record
- stage tags of `building`, `trigger_ready`, and `invalidated`
- explicit trigger and invalidation outputs

Planning implication:
- Phase 4 alerting should consume `StrategyProjection`, not raw `CandidateRow`
- watch/actionable/blocked/rejected messaging should be derived from:
  - strategy state
  - trust state
  - risk eligibility
- do not duplicate Phase 3 validity or ranking logic in Telegram or paper-broker code

### 2. Separate Telegram transport from operator decisions

The product decisions already distinguish:
- one-tap default approve
- separate adjust path
- explicit reject path

Planning implication:
- create a transport-independent approval/decision contract
- treat Telegram as one renderer/input path around that contract
- keep approval semantics explicit:
  - approve with defaults
  - adjust stop/target then approve
  - reject
  - close or adjust levels on an open trade

This keeps the workflow testable without requiring network delivery in every test.

### 3. Risk gating is a shared service, not broker-only logic

The roadmap requirement set spans:
- signal rejection for poor spread/liquidity/timing/stop distance
- fixed-risk sizing
- max daily loss
- max open positions
- cutoff time
- cooldowns

Planning implication:
- build risk and trade-quality decisions as a dedicated service layer
- evaluate that service before emitting an approval-capable Telegram alert
- evaluate it again before opening the paper trade
- emit blocked non-actionable updates when a trigger-ready setup is denied by those rules

If risk gates only live in the paper broker, the Telegram workflow cannot distinguish actionable from blocked states cleanly.

### 4. Model the paper broker as a deterministic trade state machine

The paper broker must support:
- acceptance of approved entries
- configurable slippage
- optional partial-fill support later
- automatic stop/target/early-exit behavior
- operator overrides for close/stop/target

Planning implication:
- define a paper-trade state model first
- separate entry simulation from exit management
- keep slippage configurable and partial-fill support pluggable
- express exit rules as deterministic evaluations over open-trade state plus market/strategy context

Useful state groups for planning:
- approval state
- pending/open/closed trade state
- fill assumptions
- exit cause
- operator override actions

### 5. Lifecycle persistence should be append-only and UTC-safe

Phase 5 will need:
- immutable audit logs
- paper-trade review
- P&L summaries

Planning implication:
- Phase 4 should record append-only lifecycle events rather than only final trade objects
- each event should include:
  - UTC timestamp
  - symbol / trade identity
  - event type
  - payload for operator decision, fill, rejection, adjustment, or exit
- paper-trade summaries should be derivable from those events without inventing a second truth source later

### 6. Keep Telegram messaging material and sparse

The user explicitly chose material-events-only messaging.

Planning implication:
- do not plan a streaming chatty notifier
- message classes should likely be:
  - watch
  - actionable
  - blocked/rejected update
  - trade opened
  - trade adjusted
  - trade closed / result summary
- internal rule reevaluations should update state but not necessarily emit Telegram messages

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Telegram workflow | raw chat strings tied directly to business logic | alert models + renderer + decision contract | Keeps operator behavior testable and transport-agnostic |
| Trade eligibility | checks scattered across alerts and broker methods | one shared risk/trade-gate service | Prevents alert and entry behavior from drifting apart |
| Paper trade history | only mutable “current trade” records | append-only lifecycle events plus derived summaries | Phase 5 needs reconstructable history |
| Exit handling | chat-specific manual logic embedded in broker state | explicit exit-rule evaluator plus override actions | Preserves deterministic broker behavior |
| Alert states | recomputing watch/actionable/blocked from raw fields everywhere | consume `StrategyProjection` + eligibility decisions | Reuses Phase 3 instead of duplicating it |

**Key insight:** Phase 4 should add workflow state and paper-trade state around the existing strategy scanner, not collapse alerting, risk, and broker behavior into one module.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Making Telegram the source of truth for operator decisions
**What goes wrong:** Approval logic becomes tied to message text/buttons instead of stable domain decisions.
**Why it happens:** Telegram is the first operator surface, so it is tempting to encode behavior directly in message handlers.
**How to avoid:** Model operator decisions independently of Telegram transport and let Telegram map onto that contract.
**Warning signs:** Approval semantics are only represented as message text, callback IDs, or ad hoc command parsing.

### Pitfall 2: Only checking risk gates when opening the paper trade
**What goes wrong:** Telegram sends approval-capable alerts for setups the system already knows are blocked.
**Why it happens:** Risk code is often planned as “broker logic.”
**How to avoid:** Evaluate trade-quality and session-level eligibility both before actionable alerting and before final entry open.
**Warning signs:** No separate concept of blocked trigger-ready updates exists in the alerting plan.

### Pitfall 3: Making open-trade messaging too chatty
**What goes wrong:** Telegram fills with low-value state churn and the operator stops trusting the channel.
**Why it happens:** Rule-based exit systems emit many intermediate evaluations.
**How to avoid:** Plan only material-event notifications and keep internal reevaluations silent unless state materially changes.
**Warning signs:** The plan emits alerts for every exit check, score change, or internal cooldown evaluation.

### Pitfall 4: Mixing lifecycle logging into future dashboard work
**What goes wrong:** Auditability is delayed and Phase 5 has to reconstruct past behavior from incomplete state.
**Why it happens:** Logging looks like a review/dashboard concern instead of a workflow concern.
**How to avoid:** Make append-only lifecycle events a Phase 4 deliverable and shape them for later dashboard consumption.
**Warning signs:** Phase 4 plans mention only “current trade state” and postpone signal/approval/fill/exit history.

### Pitfall 5: Letting the paper broker own strategy semantics
**What goes wrong:** Entry/exit behavior starts recomputing scanner validity and trigger logic inside paper-trade code.
**Why it happens:** The broker needs context, so strategy decisions get copied rather than consumed.
**How to avoid:** Keep broker inputs downstream of Phase 3 strategy projection and use explicit trade-gate or exit-rule inputs where needed.
**Warning signs:** Paper-broker plans mention recomputing `setup_valid`, ranking, or raw signal screening.

</common_pitfalls>
