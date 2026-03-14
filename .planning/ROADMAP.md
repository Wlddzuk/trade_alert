# Roadmap: Buy Signal

## Overview

The roadmap moves from trustworthy data and scanning foundations into strategy-specific signal detection, then into the Telegram-led paper-trading workflow, and finally into monitoring and review surfaces. This order keeps the MVP centered on scanner usefulness, operator trust, and disciplined paper validation before any live execution work is considered.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Provider Foundation** - Establish provider abstractions, runtime window, freshness rules, and initial universe filtering.
- [ ] **Phase 2: Scanner Metrics and Candidate Feed** - Build the ranked scanner row pipeline and required market/news-derived fields.
- [ ] **Phase 3: Strategy Validity and Ranking** - Add momentum pullback defaults, trigger logic, invalidations, `setup_valid`, and score/rank behavior.
- [ ] **Phase 4: Telegram Workflow and Paper Broker** - Add operator approvals, risk gates, paper fills, and exit management.
- [ ] **Phase 5: Monitoring, Audit, and Review Surface** - Add degraded-state handling, read-only dashboard, audit review, and paper P&L summaries.

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
- [ ] 01-01: Define provider interfaces, normalized records, and feed error handling
- [ ] 01-02: Implement runtime schedule and initial universe-filtering rules
- [ ] 01-03: Add basic freshness tracking and health state for provider ingestion

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
- [ ] 02-01: Build feature calculation for scanner metrics and market/news context
- [ ] 02-02: Assemble ranked candidate rows with required output fields
- [ ] 02-03: Add candidate persistence or caching needed for downstream strategy evaluation

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
- [ ] 03-01: Implement setup-valid rules and configurable strategy defaults
- [ ] 03-02: Implement trigger logic and invalidation handling
- [ ] 03-03: Implement score/rank behavior and strategy-specific why-surfaced tagging

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
- [ ] 04-01: Build Telegram alert delivery and approval workflow
- [ ] 04-02: Implement paper broker state model, entry handling, and exit handling
- [ ] 04-03: Implement risk controls, trade rejection, and cooldown behavior
- [ ] 04-04: Persist full paper-trade lifecycle events for downstream review

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
- [ ] 05-01: Implement degraded-state logic and operational monitoring surfaces
- [ ] 05-02: Implement immutable audit review and paper P&L summaries
- [ ] 05-03: Implement the secondary read-only dashboard for status, logs, and trade review

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Provider Foundation | 1/3 | In Progress|  |
| 2. Scanner Metrics and Candidate Feed | 0/3 | Not started | - |
| 3. Strategy Validity and Ranking | 0/3 | Not started | - |
| 4. Telegram Workflow and Paper Broker | 0/4 | Not started | - |
| 5. Monitoring, Audit, and Review Surface | 0/3 | Not started | - |
