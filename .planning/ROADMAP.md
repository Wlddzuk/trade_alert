# Roadmap: Buy Signal

## Overview

The roadmap moves from trustworthy data and scanning foundations into strategy-specific signal detection, then into the Telegram-led paper-trading workflow, and finally into monitoring and review surfaces. This order keeps the MVP centered on scanner usefulness, operator trust, and disciplined paper validation before any live execution work is considered.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Provider Foundation** - Establish provider abstractions, runtime window, freshness rules, and initial universe filtering. (completed 2026-03-14)
- [x] **Phase 2: Scanner Metrics and Candidate Feed** - Build the scanner row pipeline, live candidate feed state, and required market/news-derived fields. (completed 2026-03-14)
- [x] **Phase 3: Strategy Validity and Ranking** - Add momentum pullback defaults, trigger logic, invalidations, `setup_valid`, and score/rank behavior. (completed 2026-03-15)
- [x] **Phase 4: Telegram Workflow and Paper Broker** - Add operator approvals, risk gates, paper fills, and exit management. (completed 2026-03-16)
- [x] **Phase 5: Monitoring, Audit, and Review Surface** - Add degraded-state handling, read-only dashboard, audit review, and paper P&L summaries. (completed 2026-03-17)
- [x] **Phase 6: Telegram Runtime Delivery and Callback Wiring** - Wire alert delivery and operator decisions into a live Telegram transport boundary for milestone-complete workflow coverage. (completed 2026-03-18)
- [x] **Phase 7: Served Dashboard Runtime Surface** - Expose the read-only dashboard through a served application boundary so operators can access it at runtime. (completed 2026-03-18)
- [x] **Phase 8: Monitoring Verification Recovery** - Re-establish Phase 5 verification evidence so the milestone audit can mark monitoring and review requirements complete. (completed 2026-03-19)
- [x] **Phase 9: Telegram Alert Emission Closure** - Close the remaining milestone Telegram gap by wiring qualifying setup emission into outbound delivery and callback registration. (completed 2026-03-22)
- [x] **Phase 10: Dashboard Runtime Composition Closure** - Close the remaining served-dashboard integration gap by wiring a milestone-ready default runtime composition. (completed 2026-03-22)
- [ ] **Phase 11: Audit Traceability Closure** - Close the remaining verification-chain and planning-traceability gaps before milestone archival.

## Phase Details

### Phase 1: Provider Foundation
**Goal**: Establish trustworthy provider integration, runtime scheduling, and the initial scan universe without leaking vendor assumptions into core logic.
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. The system ingests Polygon.io market data and Benzinga news through separate provider interfaces.
  2. The scanner only evaluates the configured NASDAQ/NYSE common-stock universe with the defined hard filters.
  3. Runtime behavior is limited to the configured 04:00 ET to 16:30 ET window.
  4. Freshness thresholds can identify when market or news feeds are stale.
**Plans**: 3 plans

Plans:
- [x] 01-01: Define provider interfaces, normalized records, and feed error handling
- [x] 01-02: Implement runtime schedule and initial universe-filtering rules
- [x] 01-03: Add basic freshness tracking and health state for provider ingestion

### Phase 2: Scanner Metrics and Candidate Feed
**Goal**: Produce operator-usable scanner rows with the required market, news, and pullback context.
**Depends on**: Phase 1
**Requirements**: DATA-05, SCAN-01, SCAN-02, SCAN-03, SCAN-04
**Success Criteria** (what must be TRUE):
  1. Scanner rows include the required market, news, and pullback fields.
  2. Daily relative volume uses the configured baseline and short-term relative volume uses the time-of-day comparison method.
  3. Pullback % from high of day is measurable and shown in surfaced candidates.
  4. Candidate generation works during both premarket and regular session for the same initial universe.
**Plans**: 3 plans

Plans:
- [x] 02-01: Build history inputs and scanner metric calculation primitives
- [x] 02-02: Assemble symbol-centric candidate rows with latest-headline semantics
- [x] 02-03: Add live candidate-feed state, ordering, and trust-aware updates

### Phase 3: Strategy Validity and Ranking
**Goal**: Turn the candidate feed into a strategy-specific scanner by applying momentum pullback defaults, invalidations, and ranking.
**Depends on**: Phase 2
**Requirements**: SCAN-05, SCAN-06, SIG-01, SIG-02, SIG-03, SIG-04
**Success Criteria** (what must be TRUE):
  1. The system marks each candidate with a current `setup_valid` state.
  2. Default thresholds for catalyst age, move %, volume expansion, pullback range, and trigger timeframe are applied but configurable.
  3. Trigger logic uses first break of prior candle high after a valid pullback with the correct timeframe fallback.
  4. Invalid signals are suppressed when configured catalyst, volume, momentum, halt, or timing rules fail.
**Plans**: 3 plans

Plans:
- [x] 03-01: Implement setup-valid rules and configurable strategy defaults
- [x] 03-02: Implement trigger logic and invalidation handling
- [x] 03-03: Implement score/rank behavior and strategy-specific why-surfaced tagging

### Phase 4: Telegram Workflow and Paper Broker
**Goal**: Deliver the core operator loop: actionable alerts, human-approved entries, risk gates, and realistic paper fills.
**Depends on**: Phase 3
**Requirements**: SIG-05, FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05, RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06, RISK-07
**Success Criteria** (what must be TRUE):
  1. Qualifying setups are delivered to Telegram with enough context for the operator to approve or reject entry.
  2. The operator can confirm or adjust stop and target before a paper trade is opened.
  3. The paper broker applies fixed-risk sizing, slippage assumptions, and trade-quality rejection rules.
  4. Exit handling follows pre-approved rules while still allowing operator override.
**Plans**: 4 plans

Plans:
- [x] 04-01: Build Telegram alert delivery and approval workflow
- [x] 04-02: Implement paper broker state model, entry handling, and exit handling
- [x] 04-03: Implement risk controls, trade rejection, and cooldown behavior
- [x] 04-04: Persist full paper-trade lifecycle events for downstream review

### Phase 5: Monitoring, Audit, and Review Surface
**Goal**: Make the system trustworthy in use through degraded-state handling, audit review, and a read-only operator dashboard.
**Depends on**: Phase 4
**Requirements**: FLOW-06, OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Success Criteria** (what must be TRUE):
  1. The operator can see when the system is degraded or untrusted because freshness or alert-delivery thresholds are breached.
  2. Scanner loop health, error logs, and alert failures are visible for review.
  3. Immutable audit logs reconstruct each paper trade lifecycle with UTC timestamps.
  4. The dashboard provides read-only status, logs, paper-trade review, and paper P&L summaries.
**Plans**: 3 plans

Plans:
- [x] 05-01: Implement degraded-state logic and operational monitoring surfaces
- [x] 05-02: Implement immutable audit review and paper P&L summaries
- [x] 05-03: Implement the secondary read-only dashboard for status, logs, and trade review

### Phase 6: Telegram Runtime Delivery and Callback Wiring
**Goal**: Close the live operator-workflow gap by wiring Telegram alert delivery, callback handling, and override actions into the application runtime.
**Depends on**: Phase 5
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-05
**Gap Closure**: Closes milestone audit gaps for Telegram transport, callback handling, and operator override runtime flow.
**Success Criteria** (what must be TRUE):
  1. Qualifying setup alerts are sent through a production Telegram delivery adapter rather than renderer-only code paths.
  2. Operator approve, reject, stop-adjust, and target-adjust actions are accepted through a live callback or webhook path.
  3. Exit override actions can be issued through the runtime Telegram boundary and reach the workflow layer end to end.
  4. The Telegram approval and override flow is verifiable outside deterministic unit-only seams.
**Plans**: 5 plans

Plans:
- [x] 06-01: Add runtime Telegram sending adapter and delivery integration
- [x] 06-02: Implement callback or webhook handling for operator decisions
- [x] 06-03: Wire stop, target, and override actions through the live operator loop
- [x] 06-04: Serve Telegram webhook execution through the runtime app boundary
- [x] 06-05: Verify live open-trade override execution through the callback surface

### Phase 7: Served Dashboard Runtime Surface
**Goal**: Make the secondary review dashboard reachable through a served HTTP application boundary instead of render-only composition code.
**Depends on**: Phase 6
**Requirements**: FLOW-06
**Gap Closure**: Closes milestone audit gaps for dashboard runtime delivery and the secondary dashboard review flow.
**Success Criteria** (what must be TRUE):
  1. The application exposes a served HTTP entrypoint with dashboard routes registered.
  2. Operators can access the read-only dashboard at runtime to review system status, logs, and completed paper trades.
  3. The secondary dashboard review flow works through the served app boundary rather than direct renderer invocation.
  4. Dashboard runtime availability is covered by verification evidence beyond composition-only tests.
**Plans**: 2 plans

Plans:
- [x] 07-01: Register dashboard routes on a served application boundary
- [x] 07-02: Validate read-only dashboard runtime access and review flows

### Phase 8: Monitoring Verification Recovery
**Goal**: Restore milestone-audit readiness by producing the missing Phase 5 verification evidence for monitoring, audit, and review capabilities.
**Depends on**: Phase 7
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Gap Closure**: Closes milestone audit gaps for the Phase 5 evidence chain and missing verification artifact.
**Success Criteria** (what must be TRUE):
  1. Phase 5 has a complete verification report that confirms degraded-state monitoring, audit review, error visibility, and P&L reporting.
  2. Verification evidence references the served dashboard/runtime surfaces rather than only isolated tests and UAT.
  3. The milestone audit can trace monitoring and review requirements to complete verification evidence.
  4. Milestone verification flow no longer breaks on missing aggregation artifacts.
Plans:
- [x] 08-01: Re-verify Phase 5 monitoring and audit capabilities against shipped code
- [x] 08-02: Produce the missing verification artifact and trace evidence back to requirements

### Phase 9: Telegram Alert Emission Closure
**Goal**: Close the remaining Telegram runtime milestone gap by wiring qualifying setup production into outbound delivery, callback registration, and end-to-end operator entry flow evidence.
**Depends on**: Phase 6
**Requirements**: FLOW-01, FLOW-02, FLOW-03
**Gap Closure**: Closes the remaining milestone audit gaps for qualifying-alert emission and live alert-to-decision continuity.
**Success Criteria** (what must be TRUE):
  1. A qualifying setup can leave scanner/runtime code, render as a Telegram alert, send through the runtime transport, and register callback state in one production path.
  2. Approval and adjustment callbacks are verified against alert state produced by that same live emission path rather than test-only pre-registration.
  3. Telegram operator entry flow is evidenced end to end from qualifying setup to approval or adjusted approval.
  4. Milestone audit can mark `FLOW-01`, `FLOW-02`, and `FLOW-03` satisfied without relying on partial integration arguments.
**Plans**: 2 plans

Plans:
- [x] 09-01: Implement qualifying-alert emission over delivery and registry seams
- [x] 09-02: Replace partial callback proof with emission-driven approval and adjustment evidence

### Phase 10: Dashboard Runtime Composition Closure
**Goal**: Close the remaining dashboard integration gap by making the default served app compose usable auth and real monitoring/review snapshot providers for operator-facing runtime review.
**Depends on**: Phase 7
**Requirements**: FLOW-06
**Gap Closure**: Closes the remaining milestone audit gap around default runtime dashboard composition.
**Success Criteria** (what must be TRUE):
  1. The default served app no longer depends on placeholder review data for dashboard runtime behavior.
  2. Dashboard auth configuration is present at the default runtime boundary instead of requiring ad hoc injected setup to avoid a `503`.
  3. Operators can reach served overview, logs, trades, and P&L routes against real composed runtime sources in milestone verification.
  4. Milestone audit can treat the served dashboard flow as fully integrated rather than route-only.
**Plans**: 2 plans

Plans:
- [x] 10-01: Add default dashboard runtime composition and config-backed auth
- [x] 10-02: Wire real monitoring and review sources into served dashboard proof

### Phase 11: Audit Traceability Closure
**Goal**: Close the remaining verification-chain and planning-traceability gaps by publishing the missing Phase 8 verification artifact and aligning roadmap and requirements state with shipped milestone work.
**Depends on**: Phase 10
**Requirements**: None (milestone audit / verification chain)
**Gap Closure**: Closes the remaining unverified-phase and planning-traceability gaps before archival.
**Success Criteria** (what must be TRUE):
  1. Phase 8 has a definitive `08-VERIFICATION.md` artifact.
  2. ROADMAP.md and REQUIREMENTS.md reflect actual completed and pending milestone work consistently.
  3. Milestone audit can treat the verification chain as complete and internally consistent.
  4. Milestone archival is no longer blocked by missing verification artifacts or stale planning state.
**Plans**: 2 plans

Plans:
- [ ] 11-01: Publish the missing Phase 8 verification artifact
- [ ] 11-02: Reconcile roadmap, requirements, state, and milestone audit to current truth

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Provider Foundation | 3/3 | Complete    | 2026-03-14 |
| 2. Scanner Metrics and Candidate Feed | 3/3 | Complete    | 2026-03-14 |
| 3. Strategy Validity and Ranking | 3/3 | Complete    | 2026-03-15 |
| 4. Telegram Workflow and Paper Broker | 4/4 | Complete | 2026-03-16 |
| 5. Monitoring, Audit, and Review Surface | 3/3 | Complete | 2026-03-17 |
| 6. Telegram Runtime Delivery and Callback Wiring | 5/5 | Complete | 2026-03-18 |
| 7. Served Dashboard Runtime Surface | 2/2 | Complete | 2026-03-18 |
| 8. Monitoring Verification Recovery | 2/2 | Complete | 2026-03-19 |
| 9. Telegram Alert Emission Closure | 2/2 | Complete | 2026-03-22 |
| 10. Dashboard Runtime Composition Closure | 2/2 | Complete   | 2026-03-22 |
| 11. Audit Traceability Closure | 0/2 | Planned | |
