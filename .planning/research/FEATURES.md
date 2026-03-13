# Feature Research

**Domain:** operator-facing US equity momentum scanner and semi-automated paper-trading system
**Researched:** 2026-03-12
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Near-real-time scanner for news-driven movers | The core promise fails without timely candidates | HIGH | Must combine market data and news context quickly enough to matter. |
| Ranked scanner rows with catalyst and liquidity context | Operators need to decide fast without switching tools | MEDIUM | The row content is part of the product, not a cosmetic detail. |
| Actionable alerts | Scanner value drops if the operator cannot react in time | MEDIUM | Telegram-first is a good MVP fit. |
| Human-approved paper-trade workflow | Required for validating strategy and workflow before live execution | MEDIUM | Entry approval is the center of v1 discipline. |
| Trade-quality and risk gates | News-driven small caps can be mechanically untradeable | MEDIUM | Spread, liquidity, timing, and stop distance must gate signals. |
| Audit trail and paper P&L | Paper validation is not useful if trades cannot be reconstructed later | MEDIUM | Full lifecycle logging is required. |
| Operational health visibility | Operators need to know when the scanner is stale or degraded | MEDIUM | Degraded-state handling is part of trust, not an afterthought. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Strategy-specific `setup_valid` output | Makes the scanner directly usable for a specific workflow instead of generic watchlisting | MEDIUM | Strong differentiator versus generic market scanners. |
| Configurable momentum pullback thresholds | Lets the operator tune strategy defaults without rewriting core logic | MEDIUM | Important after paper-trading review cycles. |
| Venue-agnostic provider and execution boundaries | Preserves flexibility for later execution adapters and UK-relevant venues | HIGH | Architectural differentiator, not a user-facing feature. |
| Telegram-led approval flow with dashboard secondary | Matches low-latency operator behavior better than UI-heavy workflows | LOW | Clear product-shaping decision for MVP. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full auto live trading in v1 | It sounds like the fastest path to value | Adds execution, venue, and compliance complexity before the core loop is validated | Paper-trading-first with human-approved entry |
| Broad multi-asset coverage at launch | Feels larger and more capable | Dilutes scanner quality and multiplies data/provider edge cases | US equities only for MVP |
| Complex dashboard workflows | Feels more polished | Creates a second control plane before the Telegram loop is proven | Secondary read-only dashboard in v1 |
| Mandatory enrichment fields such as float and short interest | Improves context in theory | Vendor coverage and cost can block launch | Optional enhancement fields only |

## Feature Dependencies

```
[Telegram approvals]
    └──requires──> [Actionable alerts]
                       └──requires──> [Scanner rows with setup context]
                                              └──requires──> [Near-real-time news and market data]

[Paper-trade audit trail]
    └──requires──> [Paper broker workflow]
                       └──requires──> [Risk gates and stop/target handling]

[Score/rank]
    └──enhances──> [Scanner prioritization]

[Live execution adapters]
    └──conflicts with v1 focus──> [Paper-trading-first validation]
```

### Dependency Notes

- **Telegram approvals require actionable alerts:** The operator cannot approve quickly without context-rich alerts.
- **Actionable alerts require scanner rows with setup context:** Alert payloads depend on computed scanner metrics and strategy state.
- **Paper-trade audit trail requires paper broker workflow:** Full lifecycle logging depends on explicit simulated trade states.
- **Live execution conflicts with v1 focus:** It changes the product risk profile before scanner and workflow value are validated.

## MVP Definition

### Launch With (v1)

- [ ] Near-real-time US-equity scanner with required row fields — core product value
- [ ] Momentum pullback signal detection with configurable defaults — strategy validation
- [ ] Telegram-led operator approval flow — required v1 workflow
- [ ] Paper broker with slippage, risk gates, and audit trail — disciplined validation loop
- [ ] Monitoring, degraded-state handling, and read-only dashboard — required operator trust layer

### Add After Validation (v1.x)

- [ ] Stronger score/rank heuristics — add after enough paper data exists to tune
- [ ] Optional enrichment fields such as float and short interest — add when vendor coverage is reliable
- [ ] Improved review and journaling surfaces — add after baseline paper workflow is stable

### Future Consideration (v2+)

- [ ] Venue-specific execution adapters — defer until paper performance and workflow justify it
- [ ] Live execution modes — defer until strategy, controls, and venue constraints are better understood
- [ ] Additional markets and instruments — defer until the US-equities loop is proven

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Near-real-time scanner rows | HIGH | HIGH | P1 |
| Telegram alerts and approvals | HIGH | MEDIUM | P1 |
| Paper broker and risk gates | HIGH | MEDIUM | P1 |
| Monitoring and audit logs | HIGH | MEDIUM | P1 |
| Score/rank sophistication | MEDIUM | MEDIUM | P2 |
| Optional enrichment fields | MEDIUM | MEDIUM | P2 |
| Live execution adapters | HIGH | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have after core validation
- P3: Future consideration

## Competitor Feature Analysis

| Feature | Competitor A | Competitor B | Our Approach |
|---------|--------------|--------------|--------------|
| Generic scanner rows | Broad market scanners emphasize breadth | News terminals emphasize headline awareness | Focus tightly on news-driven momentum pullback context |
| Alerts | Often generic watchlist alerts | Often not strategy-specific | Make alerts directly actionable for the target setup |
| Execution | Either absent or fully broker-coupled | Often venue-locked | Keep v1 paper-first and venue-agnostic |
| Review workflow | Often spread across tools | Often operator-driven with little audit structure | Unify signal, approval, fill, exit, and result logging |

## Sources

- Product requirements gathered from project context
- Industry norms for news-driven intraday scanner workflows
- Vendor documentation for Polygon.io, Benzinga, and Telegram

---
*Feature research for: operator-facing US equity momentum scanner and semi-automated paper-trading system*
*Researched: 2026-03-12*
