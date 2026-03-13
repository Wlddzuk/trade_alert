# Phase 1: Provider Foundation - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish trustworthy provider integration, runtime scheduling, and the initial scan universe without leaking vendor assumptions into core logic.

</domain>

<decisions>
## Implementation Decisions

### Degraded mode behavior
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

</decisions>

<specifics>
## Specific Ideas

- Prioritize operator trust over continuity when inputs become stale.
- Recovery should be visible, not silent.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — the repository currently contains planning and specification documents only.

### Established Patterns
- Product scope and operator workflow are already anchored in `PRD.md`, `MVP_SCOPE.md`, and `SYSTEM_OVERVIEW.md`.
- Concrete defaults are separated into `CONFIG_DEFAULTS.md`, which should remain the source of tuneable thresholds.
- `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` already fix Phase 1 scope to provider abstraction, universe filtering, runtime window, and freshness handling.

### Integration Points
- Phase 1 planning should satisfy `DATA-01`, `DATA-02`, `DATA-03`, and `DATA-04` in `.planning/REQUIREMENTS.md`.
- Phase 1 planning should preserve the Phase 0 decisions recorded in `.planning/PROJECT.md` and `.planning/STATE.md`.
- Future phases depend on Phase 1 producing trusted provider inputs without leaking Polygon.io or Benzinga specifics into downstream scanner or strategy logic.

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-provider-foundation*
*Context gathered: 2026-03-13*
