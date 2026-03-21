# Requirements: Buy Signal

**Defined:** 2026-03-12
**Core Value:** Surface high-quality, news-driven momentum pullback opportunities early enough, with enough context and risk structure, that the operator can make faster and more consistent paper-trading decisions.

## v1 Requirements

### Data and Universe

- [x] **DATA-01**: Operator can run the scanner against a configured universe of US-listed common stocks on NASDAQ and NYSE only.
- [x] **DATA-02**: Operator can rely on hard universe filters for price and average daily volume before candidates are surfaced.
- [x] **DATA-03**: Operator can rely on near-real-time Polygon.io market-data updates during the configured runtime window.
- [x] **DATA-04**: Operator can rely on near-real-time Benzinga news updates during the configured runtime window.
- [x] **DATA-05**: Operator can see time since news and a simple catalyst classification attached to surfaced candidates.

### Scanner

- [x] **SCAN-01**: Operator can view scanner rows containing symbol, price, volume, average daily volume, gap %, % change from prior close, and why surfaced.
- [x] **SCAN-02**: Operator can view daily relative volume calculated from a configurable baseline with 20-day average as the initial default.
- [x] **SCAN-03**: Operator can view short-term relative volume using current 5-minute volume versus the 20-day time-of-day baseline.
- [x] **SCAN-04**: Operator can view pullback % from high of day for surfaced candidates.
- [x] **SCAN-05**: Operator can view a current `setup_valid` status for each surfaced candidate.
- [x] **SCAN-06**: Operator can view a score/rank that prioritizes surfaced candidates.

### Strategy and Signal Quality

- [x] **SIG-01**: Operator receives setup candidates only when recent catalyst, day move, and volume expansion pass configured defaults.
- [x] **SIG-02**: Operator receives setup candidates only when pullback retracement remains within the configured valid range.
- [x] **SIG-03**: Operator receives a trigger when price first breaks the prior candle high after a valid pullback, with 15-second data preferred and 1-minute fallback.
- [x] **SIG-04**: Operator does not receive a trigger when invalidation conditions are active, including stale or contradictory catalyst, weak volume, halt state, or excessive pullback.
- [x] **SIG-05**: Operator can rely on signals being rejected when spread, liquidity, timing, or stop-distance conditions make the setup poor quality.

### Alerts and Operator Workflow

- [ ] **FLOW-01**: Operator receives qualifying setup alerts in Telegram.
- [ ] **FLOW-02**: Operator can approve or reject a paper entry through the Telegram-led workflow.
- [ ] **FLOW-03**: Operator can confirm or adjust stop and target when approving an entry.
- [x] **FLOW-04**: Operator can allow exits to follow pre-approved rules after entry.
- [x] **FLOW-05**: Operator can override exit behavior at any time.
- [x] **FLOW-06**: Operator can review system status, logs, and completed paper trades in a secondary read-only dashboard.

### Risk and Paper Trading

- [x] **RISK-01**: Operator sizes paper entries using fixed % risk of paper account equity.
- [x] **RISK-02**: Operator cannot enter a paper trade without a required stop.
- [x] **RISK-03**: Operator cannot exceed max daily loss or max open position limits in v1.
- [x] **RISK-04**: Operator cannot open new entries after the configured cutoff time.
- [x] **RISK-05**: Operator is subject to cooldown rules after losses and consecutive losses.
- [x] **RISK-06**: Paper fills simulate configured slippage assumptions.
- [x] **RISK-07**: Paper broker architecture supports optional partial-fill simulation even if disabled by default.

### Monitoring and Audit

- [x] **OPS-01**: Operator can see when the system is degraded or untrusted because data freshness or alert-delivery thresholds are breached.
- [x] **OPS-02**: Operator can rely on scanner loop health being monitored during runtime.
- [x] **OPS-03**: Operator can review immutable audit logs with UTC timestamps for each paper trade lifecycle.
- [x] **OPS-04**: Operator can review paper P&L summaries.
- [x] **OPS-05**: Operator can review error logs for data, scanner, and alert failures.

## v2 Requirements

### Execution and Expansion

- **EXEC-01**: Operator can use venue-specific execution adapters.
- **EXEC-02**: Operator can opt into live execution modes after paper validation.
- **MARK-01**: Operator can expand the system beyond US equities into additional markets and instruments.
- **ENRH-01**: Operator can use optional enrichment fields such as float, short interest, and supply proxy when vendor coverage is reliable.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Fully automated live trading in v1 | Paper mode and operator workflow must be validated first |
| Dashboard as primary approval/control surface | Telegram is the intended operator workflow in v1 |
| Non-US-equity markets in v1 | Scope is intentionally narrow around US equities |
| Mandatory enrichment fields for launch | Vendor cost and coverage should not block MVP |
| 24/7 runtime | MVP only needs premarket plus regular-session operation |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 2 | Complete |
| SCAN-01 | Phase 2 | Complete |
| SCAN-02 | Phase 2 | Complete |
| SCAN-03 | Phase 2 | Complete |
| SCAN-04 | Phase 2 | Complete |
| SCAN-05 | Phase 3 | Complete |
| SCAN-06 | Phase 3 | Complete |
| SIG-01 | Phase 3 | Complete |
| SIG-02 | Phase 3 | Complete |
| SIG-03 | Phase 3 | Complete |
| SIG-04 | Phase 3 | Complete |
| SIG-05 | Phase 4 | Complete |
| FLOW-01 | Phase 9 | Pending |
| FLOW-02 | Phase 9 | Pending |
| FLOW-03 | Phase 9 | Pending |
| FLOW-04 | Phase 4 | Complete |
| FLOW-05 | Phase 6 | Complete |
| FLOW-06 | Phase 10 | Pending |
| RISK-01 | Phase 4 | Complete |
| RISK-02 | Phase 4 | Complete |
| RISK-03 | Phase 4 | Complete |
| RISK-04 | Phase 4 | Complete |
| RISK-05 | Phase 4 | Complete |
| RISK-06 | Phase 4 | Complete |
| RISK-07 | Phase 4 | Complete |
| OPS-01 | Phase 8 | Complete |
| OPS-02 | Phase 8 | Complete |
| OPS-03 | Phase 8 | Complete |
| OPS-04 | Phase 8 | Complete |
| OPS-05 | Phase 8 | Complete |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-20 after milestone gap planning*
