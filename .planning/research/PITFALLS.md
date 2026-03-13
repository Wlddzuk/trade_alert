# Pitfalls Research

**Domain:** operator-facing US equity momentum scanner and semi-automated paper-trading system
**Researched:** 2026-03-12
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Stale Data Presented as Live Opportunity

**What goes wrong:**
The scanner surfaces rows that look current even though market or news updates have gone stale.

**Why it happens:**
Teams treat freshness as an ops concern instead of part of product trust.

**How to avoid:**
Track explicit freshness thresholds, expose degraded/untrusted state, and suppress trust in signals when thresholds are breached.

**Warning signs:**
Rows continue changing less often than expected, news timestamps stop advancing, or alerts keep sending while feeds are stale.

**Phase to address:**
Phase 1 and Phase 5

---

### Pitfall 2: Provider Lock-In Hidden in Core Logic

**What goes wrong:**
Polygon- or Benzinga-specific assumptions leak into scanner, ranking, or workflow code.

**Why it happens:**
Provider payloads are convenient to use directly during early development.

**How to avoid:**
Normalize all provider data immediately behind explicit interfaces and keep adapter logic isolated.

**Warning signs:**
Core services reference vendor field names directly or require vendor-specific branching.

**Phase to address:**
Phase 1

---

### Pitfall 3: Scanner Quality Degrades from Universe Creep

**What goes wrong:**
The system starts scanning too broad a universe too early and becomes noisy or slow.

**Why it happens:**
Teams assume broader coverage equals better coverage.

**How to avoid:**
Keep the initial universe narrow, enforce hard filters, and prioritize news-driven movers explicitly.

**Warning signs:**
Too many low-quality symbols, poor operator trust, or scan cadence struggling to stay within targets.

**Phase to address:**
Phase 1 and Phase 2

---

### Pitfall 4: Trigger Rules Become Pattern Soup

**What goes wrong:**
The strategy accumulates too many candle patterns and subjective exceptions before validation.

**Why it happens:**
Teams overfit the strategy in spec form instead of validating a measurable baseline first.

**How to avoid:**
Start with explicit defaults and a simple measurable trigger, then tune only after paper-trading review.

**Warning signs:**
Frequent additions of one-off pattern rules or inability to explain why a trigger fired.

**Phase to address:**
Phase 3

---

### Pitfall 5: Paper Broker Assumes Unrealistic Fills

**What goes wrong:**
Paper results look strong because fills ignore spread, slippage, and liquidity realities.

**Why it happens:**
Teams treat paper mode as just a database write, not a realism problem.

**How to avoid:**
Model slippage explicitly, enforce spread and liquidity guardrails, and keep partial-fill behavior available even if off by default.

**Warning signs:**
High paper win rate with entries that would be poor in live conditions, or no rejected trades despite weak liquidity.

**Phase to address:**
Phase 4

---

### Pitfall 6: Dashboard Scope Creep

**What goes wrong:**
The dashboard expands into a full workflow platform before the Telegram approval loop is proven.

**Why it happens:**
A visible UI feels like progress, even when it is not the main operator path.

**How to avoid:**
Keep the dashboard read-only in v1 and let Telegram remain the primary workflow.

**Warning signs:**
Approval, editing, and control features begin moving into the dashboard before the core loop is stable.

**Phase to address:**
Phase 4 and Phase 5

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coding provider assumptions | Faster first integration | Painful vendor replacement later | Never acceptable |
| Skipping audit detail in paper mode | Faster initial workflow | Weak review and tuning later | Never acceptable |
| Deferring degraded-state handling | Fewer early health rules | Operator trust collapses when feeds misbehave | Never acceptable |
| Keeping partial fills off by default | Simpler MVP simulation | Slightly less realism | Acceptable in v1 if architecture supports enabling later |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Polygon.io | Treating feed timing as always continuous | Measure freshness explicitly and handle degraded state |
| Benzinga | Losing headline context during classification | Store both headline text and simple catalyst classification |
| Telegram | Assuming delivery succeeded without retries or failure state | Track retries and mark alert failures clearly |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Scanning too broad a universe | Slow loops and noisy results | Keep hard universe filters and news-first prioritization | Early in MVP if filters are relaxed |
| Computing expensive metrics on every symbol without staging | Scan cadence drifts above target | Separate filtering from heavy computations | Once symbol count rises or cadence tightens |
| Heavy dashboard queries on the same path as live scan logic | Operator UI affects scanner responsiveness | Isolate review queries from scan execution paths | As audit volume grows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing provider secrets in logs or dashboard | Credential leakage | Strict secret handling and log hygiene |
| Treating Telegram operator actions as implicitly trusted without validation | Workflow spoofing or bad state transitions | Validate message origin and allowed transitions |
| Weak audit immutability | Poor review credibility | Store UTC timestamps and append-only lifecycle records |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Alerts omit trade context | Operator cannot act quickly | Include why surfaced, catalyst, setup status, entry, stop, target, and score/rank |
| System hides degraded state | Operator trusts stale signals | Make degraded/untrusted state obvious |
| Too many low-quality alerts | Operator ignores the system | Keep ranking and invalidation disciplined |

## "Looks Done But Isn't" Checklist

- [ ] **Scanner rows:** Often missing clear why-surfaced explanations — verify row context is operator-usable.
- [ ] **Alerts:** Often missing enough trade context — verify stop, target, and setup status are included.
- [ ] **Paper broker:** Often missing realistic rejection behavior — verify spread, liquidity, and stop-distance gates exist.
- [ ] **Monitoring:** Often missing degraded-state operator visibility — verify trust state appears in the operator surface.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Stale feed trust issue | MEDIUM | Suppress trust state, review freshness logs, re-enable only after provider recovery |
| Provider lock-in | HIGH | Introduce normalization boundary, refactor core services off vendor fields |
| Unrealistic paper fills | MEDIUM | Tighten simulation defaults, rerun paper reviews, compare before/after outcomes |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Stale data presented as live | Phase 1 and Phase 5 | Freshness thresholds and degraded-state behavior work |
| Provider lock-in | Phase 1 | Core scanner and workflow logic no longer reference vendor payload shapes |
| Universe creep | Phase 1 and Phase 2 | Scan cadence and candidate quality remain within targets |
| Pattern soup | Phase 3 | Trigger logic stays measurable and configurable |
| Unrealistic paper fills | Phase 4 | Rejected trades and slippage assumptions appear in audit trail |
| Dashboard scope creep | Phase 5 | Dashboard remains read-only in v1 |

## Sources

- Project requirements and defaults
- Provider documentation and operator workflow decisions
- Known failure modes in alerting, market-data, and paper-simulation systems

---
*Pitfalls research for: operator-facing US equity momentum scanner and semi-automated paper-trading system*
*Researched: 2026-03-12*
