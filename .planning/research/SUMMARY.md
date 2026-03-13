# Project Research Summary

**Project:** Buy Signal
**Domain:** operator-facing US equity momentum scanner and semi-automated paper-trading system
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

This project fits a common pattern: a market-data and news-ingestion backend, a deterministic scanner and signal engine, a narrow operator workflow, and a strong audit layer. The recommended MVP approach is to keep the core focused on near-real-time US-equity scanning, Telegram-led human approvals, and paper-trade simulation, while resisting pressure to broaden scope into multi-market coverage, live execution, or a workflow-heavy dashboard.

The main research implication is that trust is part of the product. Freshness thresholds, degraded-state handling, trade-quality gates, and realistic paper simulation are not secondary engineering concerns; they are necessary for the operator to trust the scanner enough to use it. Provider and execution abstraction should be designed in from the start, but only enough to preserve optionality rather than to support immediate multi-venue breadth.

## Key Findings

### Recommended Stack

The strongest MVP stack is Python/FastAPI for backend services, PostgreSQL for durable state and audit, Redis for transient workflow state, and a thin Next.js dashboard for read-only operator review. This fits the single-VM constraint, keeps scanner and strategy code in a Python-first environment, and avoids overengineering for scale the product does not need yet.

**Core technologies:**
- Python — scanner, strategy, provider, and workflow runtime
- FastAPI — API and service boundary
- PostgreSQL — persistent records, audit, and review
- Redis — retries, cooldowns, and scan/runtime state
- Next.js — secondary read-only dashboard

### Expected Features

The table stakes are a near-real-time scanner, context-rich rows, actionable alerts, human-approved paper entries, risk gates, and a full audit trail. Differentiators come from making the scanner directly useful for a specific news-driven momentum pullback workflow rather than shipping a generic market scanner.

**Must have (table stakes):**
- Near-real-time scanner rows with catalyst and liquidity context
- Telegram-led operator alerts and approvals
- Paper broker with risk controls and audit trail
- Monitoring and degraded-state handling

**Should have (competitive):**
- `setup_valid` and strategy-specific why-surfaced tagging
- Configurable defaults for ranking and setup logic
- Venue-agnostic provider and execution boundaries

**Defer (v2+):**
- Venue-specific execution adapters
- Live automated execution
- Broader multi-market coverage

### Architecture Approach

The recommended architecture is a deterministic signal pipeline with explicit provider boundaries, clear separation between scanner metrics and strategy rules, and a Telegram-led human approval loop. The dashboard should remain a secondary read-only surface until the core loop is proven.

**Major components:**
1. Provider and ingestion layer — market/news collection and normalization
2. Scanner and strategy layer — metrics, ranking, setup validity, and invalidations
3. Workflow and paper broker layer — alerts, approvals, simulated fills, and exits
4. Monitoring and audit layer — freshness, degraded state, logs, and review

### Critical Pitfalls

1. **Stale data presented as live** — solve with explicit freshness thresholds and degraded-state handling.
2. **Provider lock-in** — solve with normalization behind separate provider interfaces.
3. **Universe creep and noisy scans** — solve with strict initial universe filters and news-first prioritization.
4. **Pattern-heavy overfitting before validation** — solve with measurable defaults and post-paper tuning.
5. **Unrealistic paper fills** — solve with slippage, spread, and liquidity controls from the start.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Provider Foundation
**Rationale:** Provider abstraction, feed freshness, and universe control must exist before the scanner can be trusted.
**Delivers:** Market/news adapters, runtime schedule, freshness rules, and initial universe filtering.
**Addresses:** Core data and trust foundations.
**Avoids:** Provider lock-in and stale-data trust failures.

### Phase 2: Scanner Metrics and Candidate Feed
**Rationale:** The operator needs usable ranked rows before deeper workflow work matters.
**Delivers:** Scanner fields, pullback context, and candidate generation.
**Uses:** Provider outputs and feature calculations.
**Implements:** Scanner and row-building components.

### Phase 3: Strategy Validity and Ranking
**Rationale:** The product must become strategy-specific rather than remaining a generic scanner.
**Delivers:** Default thresholds, trigger logic, invalidations, `setup_valid`, and score/rank.
**Uses:** Scanner metrics and configurable defaults.
**Implements:** Strategy and trade-quality components.

### Phase 4: Operator Workflow and Paper Broker
**Rationale:** Once candidates are good enough, the operator loop and paper simulation become the next source of product value.
**Delivers:** Telegram alerts, human approvals, stop/target confirmation, risk gates, and paper fills.
**Uses:** Strategy signals and risk defaults.
**Implements:** Alerting, approvals, and paper execution.

### Phase 5: Monitoring, Audit, and Review
**Rationale:** The scanner must remain trustworthy in use, not just in demos.
**Delivers:** Degraded state, audit logs, paper P&L summaries, and read-only dashboard review.
**Uses:** Workflow and paper-trade records.
**Implements:** Monitoring, audit, and review surfaces.

### Phase Ordering Rationale

- Data trust and provider isolation come before scanner sophistication.
- Scanner usefulness comes before UI depth.
- Strategy-specific rules come before execution-like workflow.
- Monitoring and review are essential before the product can be treated as a dependable operator tool.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** score/rank design and operational definitions for the remaining soft invalidation rules
- **Phase 4:** realistic paper-fill behavior as operator review data accumulates

Phases with standard patterns:
- **Phase 1:** provider abstraction, freshness monitoring, and runtime control
- **Phase 2:** scanner row construction and metric calculation
- **Phase 5:** audit logging and degraded-state monitoring

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Stack is a strong fit, though exact library choices can still change before implementation |
| Features | HIGH | Product scope and operator workflow are already well defined |
| Architecture | HIGH | Boundaries and build order are clear for MVP |
| Pitfalls | HIGH | The main failure modes are evident from the product shape |

**Overall confidence:** HIGH

### Gaps to Address

- Score/rank design still needs an explicit first model.
- Soft trade-quality definitions still need measurable rule wording.

## Sources

### Primary (HIGH confidence)
- Project PRD, MVP scope, system overview, and defaults
- Official docs for Polygon.io, Benzinga, FastAPI, PostgreSQL, Redis, Next.js, and Telegram

### Secondary (MEDIUM confidence)
- Common architecture patterns for operator-facing scanner and alert systems

### Tertiary (LOW confidence)
- None material at this stage

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
