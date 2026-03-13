# Phase 1: Provider Foundation - Research

**Researched:** 2026-03-13
**Domain:** provider abstraction, runtime scheduling, universe filtering, and trust-state handling for a scanner-first US-equity trading system
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- If market-data freshness or news freshness breaches its configured threshold during the runtime window, the system must pause new scanner signals.
- The system must not allow partial actionable signals when only one provider is healthy; both market data and news must be trusted before surfacing actionable candidates.
- Degraded state must be communicated in both operator surfaces used in v1:
  - Telegram receives a system-status alert.
  - The secondary dashboard shows a persistent degraded/untrusted state.
- When provider freshness returns to normal, the system may auto-resume scanning, but it must send an explicit recovery notice so the operator knows trust has been restored.

### Claude's Discretion
- Exact degraded-state wording, severity labels, and alert copy.
- Whether stale rows remain visible in read-only surfaces while the system is degraded, as long as no new actionable signals are emitted.
- Runtime warm-up and shutdown details within the already-decided 04:00 ET to 16:30 ET window.
- Handling for borderline universe cases not explicitly decided yet, such as incomplete metadata or limited trading history, provided the hard NASDAQ/NYSE common-stock universe and price/ADV filters remain intact.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.

</user_constraints>

<research_summary>
## Summary

Phase 1 is the trust boundary for the whole product. The planner should treat it as a foundation phase that establishes clean provider contracts, a narrow and reliable market universe, an explicit runtime window, and a system-level health model that later phases can depend on. This phase should not attempt scanner ranking, trigger logic, or paper-trade behavior beyond what is necessary to make provider inputs trustworthy and portable.

The standard approach for a system shaped like this is to normalize vendor payloads immediately behind separate provider interfaces and keep all downstream logic vendor-agnostic. Runtime gating and degraded-state logic should be product behavior, not just internal monitoring. If the system cannot trust both market and news inputs, it should stop producing actionable outcomes rather than degrade silently.

**Primary recommendation:** Plan Phase 1 as three focused plans: provider contracts and normalized models, runtime window plus universe filters, and freshness/degraded-state tracking.
</research_summary>

<architecture_patterns>
## Phase Architecture Guidance

### 1. Provider boundaries should follow internal capabilities, not vendor endpoints

The planner should define interfaces around what the core system needs from providers, not around raw Polygon.io or Benzinga API shapes. This keeps the core logic stable if providers change later.

Recommended internal provider capabilities:
- `MarketDataProvider`
  - fetch or stream the latest market records for the configured universe
  - expose provider timestamp metadata needed for freshness tracking
  - expose symbol/instrument metadata or integrate with a separate reference-data source
- `NewsProvider`
  - fetch recent news items relevant to configured symbols
  - preserve headline text, publish timestamp, provider identifier, and simple catalyst tag/classification
  - expose provider timestamp metadata needed for freshness tracking

Recommended planning rule:
- vendor-specific request/response logic lives only in adapter modules
- normalized models live in shared internal schemas
- scanner and strategy layers must not reference vendor field names directly

### 2. Normalized records should be future-proof enough for Phases 2 and 3

Phase 1 should not overdesign the entire downstream data model, but it should define stable internal shapes that will support scanner metrics without needing an early refactor.

Recommended normalized record families:
- `InstrumentRecord`
  - symbol
  - exchange
  - asset type / security type
  - common-stock eligibility flags
  - average daily volume
  - optional enrichment availability flags
- `MarketTick` or `MarketSnapshot`
  - symbol
  - timestamp_utc
  - last price
  - session volume
  - day high / low if available
  - prior close or enough information to compute later scanner fields
- `NewsEvent`
  - provider event id
  - published_at_utc
  - received_at_utc
  - related symbols
  - headline
  - simple catalyst tag/classification
  - contradiction/retraction indicator if provider supports it later
- `ProviderHealthSnapshot`
  - provider name
  - observed_at_utc
  - last_update_at_utc
  - freshness_age_seconds
  - health state
  - reason

Planning implication:
- choose internal models that are minimal but explicit
- include UTC timestamps in every normalized record
- keep provider-specific raw payload preservation optional, not a Phase 1 requirement

### 3. Runtime scheduling should use ET for business rules and UTC for storage

The product schedule is defined in US market time, but internal storage and comparisons should use UTC to avoid ambiguity.

Planning recommendation:
- schedule rules are configured in ET
- persisted timestamps are stored in UTC
- runtime state distinguishes at least:
  - outside window
  - premarket active
  - regular session active
  - stopped / after cutoff

Expected runtime behavior for planning:
- before `04:00 ET`: no active scanner polling
- `04:00 ET` to `16:30 ET`: provider polling and freshness tracking active
- after `16:30 ET`: no new scanner activity for v1
- after-hours scanning is explicitly out of scope for this phase

Warm-up and shutdown are still at planner discretion, but the plan should include explicit behavior at the edges of the configured window rather than assuming continuous runtime.

### 4. Universe filtering should fail closed when eligibility cannot be trusted

The universe is already decided: NASDAQ/NYSE common stocks only, with hard price and ADV filters. The main gray area is how to handle incomplete or borderline metadata.

Recommended planning posture:
- use exclusion-by-attributes, not symbol-name heuristics
- treat missing or ambiguous eligibility metadata as ineligible until proven valid
- treat missing ADV data as failing the hard filter
- keep market cap out of the hard filter path in v1

Edge cases the planner should handle explicitly:
- symbol is on NASDAQ/NYSE but security type is unclear
- symbol lacks enough history to compute ADV reliably
- symbol passes exchange checks but belongs to an excluded instrument type
- symbol metadata is stale or partially unavailable during runtime

This fail-closed posture is better aligned with operator trust than trying to rescue borderline symbols during the foundation phase.

### 5. Degraded state is part of the product contract

Freshness and trust behavior should be modeled as explicit system state, not buried in logs. The planner should design Phase 1 so later phases can query a single source of truth for provider health.

Recommended internal health states:
- `healthy`
- `degraded`
- `recovering` or equivalent transitional state if useful

Phase 1 planning should ensure:
- provider freshness is measured independently for market and news
- overall actionable trust requires both providers healthy
- new actionable output is gated off while degraded
- recovery generates a visible system event

Important scope guard:
- alert-delivery health belongs to later workflow/monitoring phases
- Phase 1 only needs provider freshness and provider-derived trust state

### 6. Sequence the phase to protect downstream optionality

The safest planning order is:
1. provider interfaces and normalized schemas
2. runtime window and universe eligibility rules
3. provider freshness tracking and degraded-state logic

This sequence matches the roadmap and minimizes rework:
- scanner metrics depend on normalized inputs
- scan cadence depends on runtime behavior
- trusted signals later depend on health-state gating that is defined here

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timezone and session math | Ad-hoc string/date comparisons | standard timezone-aware datetime handling with explicit ET/UTC conversion | Market-session boundaries are easy to get subtly wrong |
| Provider field usage in core logic | direct scanner access to vendor payloads | normalized internal schemas at the adapter boundary | Prevents provider lock-in and test fragility |
| Eligibility inference from ticker strings | symbol-pattern guesses | explicit exchange/security-type metadata | Symbol heuristics are brittle and create false inclusions |

**Key insight:** This phase should hand-roll as little market/session plumbing as possible beyond the business rules that are product-specific.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Provider schemas leak into core planning
**What goes wrong:** Phase 1 plans treat Polygon.io and Benzinga payloads as the source of truth instead of defining internal records first.
**Why it happens:** Vendor payloads are convenient during initial integration.
**How to avoid:** Put schema definition and adapter boundaries in the first plan.
**Warning signs:** Future plan tasks reference vendor field names outside provider modules.

### Pitfall 2: Session boundaries are left implicit
**What goes wrong:** The system is described as running during market hours, but startup, stop, and out-of-window behavior are not codified.
**Why it happens:** Scheduling feels operational instead of product-facing.
**How to avoid:** Treat schedule behavior as part of Phase 1 acceptance criteria.
**Warning signs:** No explicit task covers window transitions or outside-window behavior.

### Pitfall 3: Universe filters are defined but not enforceable
**What goes wrong:** Requirements say NASDAQ/NYSE common stocks only, but the plan lacks a clear eligibility model or fallback for missing metadata.
**Why it happens:** Teams assume vendor metadata is always complete.
**How to avoid:** Make fail-closed eligibility and missing-data handling explicit.
**Warning signs:** Plans mention filters but do not define what happens when metadata is incomplete.

### Pitfall 4: Freshness is tracked but not connected to trust state
**What goes wrong:** Health metrics exist, but they do not gate actionable output or produce operator-facing state.
**Why it happens:** Health is treated as internal telemetry only.
**How to avoid:** Build a provider-health model that directly drives degraded/untrusted status.
**Warning signs:** Plans talk about timestamps and polling but never about system state transitions.
</common_pitfalls>

<validation_architecture>
## Validation Architecture

Phase 1 is the first implementation phase, so the plan should include early test infrastructure rather than assuming it already exists.

Recommended validation posture:
- use `pytest` as the Phase 1 test framework, aligned with the project stack recommendation
- favor deterministic unit and service-level tests with canned provider payload fixtures
- avoid live external-provider calls in automated tests
- validate business-time behavior with explicit ET-to-UTC cases

Coverage the planner should ensure exists by the end of the phase:
- provider normalization tests
  - Polygon.io payloads normalize into internal market records
  - Benzinga payloads normalize into internal news records
- universe eligibility tests
  - included vs excluded instrument types
  - missing metadata fails closed
  - price and ADV hard filters behave as configured
- runtime schedule tests
  - before open, active window, and after cutoff behavior
  - ET/UTC conversion around session edges
- provider health tests
  - healthy to degraded transition on stale updates
  - degraded blocks actionable outputs
  - recovery returns to trusted state and emits a recovery event

Recommended testing pattern for planning:
- quick verification command should target only backend/provider foundation tests
- full verification command can remain the whole backend test suite once it exists
- if test infrastructure is absent, Wave 0 or the earliest Phase 1 plan must establish the minimal backend test harness

Manual verification should be minimal in this phase. Most Phase 1 behavior is deterministic and should be testable without UI-driven checks.
</validation_architecture>

<planning_recommendations>
## Planning Recommendations

### Recommended plan split

- `01-01` Provider contracts, normalized schemas, and provider-side error handling
- `01-02` Runtime window behavior and enforceable universe filtering
- `01-03` Freshness tracking, provider health state, and degraded/untrusted gating

### Recommended dependency shape

- `01-01` should execute first because later plans depend on shared models/contracts
- `01-02` can depend on `01-01`
- `01-03` should depend on at least `01-01`, and likely `01-02` if health state needs runtime-window integration

### Out-of-scope guardrails for the planner

Do not pull these into Phase 1 plans:
- scanner row ranking or score logic
- `setup_valid` or trigger logic
- Telegram alert delivery mechanics beyond noting future degraded-state integration
- paper-trade workflow
- optional enrichment fields like float or short interest
</planning_recommendations>

<open_questions>
## Open Questions

1. **How much raw provider payload should be retained alongside normalized records?**
   - What we know: normalized internal records are required
   - What's unclear: whether raw payload storage is worth adding in Phase 1
   - Recommendation: treat raw payload retention as optional and keep it out of the critical path unless it materially helps debugging

2. **Should borderline instrument-eligibility failures be logged as normal exclusions or elevated warnings?**
   - What we know: they should fail closed
   - What's unclear: how noisy operator-facing or developer-facing logging should be
   - Recommendation: keep this at planner discretion and prefer internal logging over operator noise in v1
</open_questions>

<sources>
## Sources

### Primary
- `.planning/phases/01-provider-foundation/01-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/PROJECT.md`
- `.planning/STATE.md`
- `CONFIG_DEFAULTS.md`
- `SYSTEM_OVERVIEW.md`
- `.planning/research/STACK.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`

### Secondary
- Existing project-level research synthesized on 2026-03-12
</sources>

<metadata>
## Metadata

**Research scope:**
- provider abstraction boundaries
- normalized records
- runtime scheduling
- universe eligibility
- freshness and degraded state
- validation strategy for the first implementation phase

**Confidence breakdown:**
- Provider boundaries: HIGH
- Runtime/session behavior: HIGH
- Universe filtering posture: HIGH
- Validation strategy: MEDIUM

**Research date:** 2026-03-13
**Valid until:** 2026-04-12
</metadata>

---

*Phase: 01-provider-foundation*
*Research completed: 2026-03-13*
*Ready for planning: yes*
