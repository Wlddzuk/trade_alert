# Phase 8: Monitoring Verification Recovery - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Restore milestone-audit readiness by producing the missing Phase 5 verification evidence for monitoring, audit, and review capabilities.

This phase decides how the missing verification artifact should be rebuilt and what evidence should count. It does not add new monitoring features, redesign the dashboard, or reopen Telegram runtime scope beyond what later phases already shipped.

</domain>

<decisions>
## Implementation Decisions

### Evidence scope
- Phase 8 should rebuild a full Phase 5 verification story, not just the smallest possible audit patch.
- The recovered verification must account for all Phase 5 monitoring, audit, and review requirements:
  - `OPS-01`
  - `OPS-02`
  - `OPS-03`
  - `OPS-04`
  - `OPS-05`
- The recovered artifact should rely on:
  - automated tests
  - current-code inspection
  - served-dashboard/runtime proof where relevant
- Existing Phase 5 summaries, UAT, validation, and tests should be reused as evidence inputs and consolidated into the recovered verification report rather than discarded.
- Requirement traceability should be explicit and requirement-by-requirement inside the recovered verification artifact.

### Cross-phase evidence posture
- Phase 8 should verify the current codebase as it exists now, not try to reconstruct a frozen pre-Phase-7 state.
- Phase 7 served-dashboard evidence is required supporting evidence for the recovered Phase 5 verification story wherever runtime review access matters.
- Phase 7 runtime proof should be treated as downstream confirmation of the Phase 5 review surface, not as a replacement for Phase 5’s original monitoring and audit evidence.
- Phase 8 should stay centered on dashboard, monitoring, logs, audit review, and paper P&L evidence; it should not broaden into Telegram runtime proof from Phase 6 except where alert-delivery health already matters to Phase 5 monitoring surfaces.

### Verification artifact shape
- The main output should be one definitive, audit-facing `05-VERIFICATION.md`.
- The recovered report should explicitly state the old gap, then show how the current evidence closes it.
- The report should be easy for the milestone audit to cite directly rather than relying on a separate appendix or recovery note.
- The recovered report should include a short residual-risk section for non-blocking caveats.

### Acceptance posture
- Phase 8 can pass once every Phase 5 OPS requirement is explicitly evidenced in the recovered verification report.
- Passing evidence should be based on automated proof plus traceable report synthesis, not a broad re-run of historical manual flows.
- If any manual check is still useful, it should stay limited to a light visual sanity check of the served read-only dashboard rather than a deep manual workflow retest.
- Once Phase 8 passes, it should explicitly close the milestone audit gap around the missing Phase 5 verification artifact.

### Already-fixed inputs that Phase 8 must honor
- Phase 5 already defined the monitoring, audit, and read-only dashboard behavior that needs to be evidenced.
- Phase 7 already established the served dashboard/runtime surface and produced runtime verification evidence for `FLOW-06`.
- Phase 8 is about evidence recovery and audit traceability, not about changing the shipped product scope.

### Claude's Discretion
- Exact structure of the recovered verification report, as long as it stays requirement-mapped, audit-facing, and gap-closing.
- Exact balance between concise narrative and traceability tables, as long as the missing evidence chain becomes easy to audit.
- Exact list of supporting test commands and code references, as long as each required capability is tied to concrete proof.

</decisions>

<specifics>
## Specific Ideas

- Treat the old milestone audit as the problem statement: Phase 8 should explicitly resolve the missing `05-VERIFICATION.md` gap rather than writing a generic report.
- Use the served dashboard/runtime proof from Phase 7 as the final runtime evidence chain for review access instead of pretending Phase 5 still exists only at renderer level.
- Keep the recovery artifact honest: acknowledge non-blocking caveats briefly, but do not let them blur whether the OPS requirements are actually evidenced.
- Optimize the output for milestone closure, not for adding a second layer of planning prose.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/v1.0-MILESTONE-AUDIT.md`
  - Already enumerates the exact missing verification gap for Phase 5 and the OPS/FLOW requirements affected.
- `.planning/phases/05-monitoring-audit-and-review-surface/05-UAT.md`
  - Existing user-acceptance evidence can be reused as one input to the recovered verification story.
- `.planning/phases/05-monitoring-audit-and-review-surface/05-01-SUMMARY.md`
  - Summarizes the shipped ops monitoring read models tied to `OPS-01`, `OPS-02`, and `OPS-05`.
- `.planning/phases/05-monitoring-audit-and-review-surface/05-02-SUMMARY.md`
  - Summarizes the shipped immutable audit review and paper P&L read models tied to `OPS-03` and `OPS-04`.
- `.planning/phases/05-monitoring-audit-and-review-surface/05-03-SUMMARY.md`
  - Summarizes the read-only dashboard composition over those Phase 5 read models.
- `.planning/phases/07-served-dashboard-runtime-surface/07-VERIFICATION.md`
  - Already provides served runtime evidence for the dashboard review flow that the recovered Phase 5 verification should cite where runtime access matters.
- `backend/tests/ops_dashboard/`, `backend/tests/audit_review/`, and `backend/tests/dashboard/`
  - Already contain the main automated evidence seams the recovery report should synthesize.

### Established Patterns
- Prior phases treat verification as a requirement-mapped artifact rather than a loose summary.
- Monitoring and review behavior in this repo is already backed by deterministic tests and immutable/read-model-oriented contracts.
- Dashboard runtime delivery is now verified through the served ASGI boundary, not only through direct rendering helpers.

### Integration Points
- Phase 8 should connect the milestone audit gap list, Phase 5 summaries/UAT/tests, and Phase 7 served-dashboard verification into one coherent `05-VERIFICATION.md`.
- The recovered Phase 5 verification should feed back into milestone audit readiness by making `OPS-01` through `OPS-05` auditable as complete evidence chains.
- Planning should account for any audit-file or traceability updates needed once the recovered verification artifact exists.

</code_context>

<deferred>
## Deferred Ideas

- Expanding monitoring features or adding new observability signals would be a new phase, not part of this recovery work.
- Reopening Telegram runtime delivery evidence as a major focus is outside this phase unless needed only as secondary context for Phase 5 monitoring.
- Reworking dashboard UX or auth beyond lightweight sanity verification remains outside scope.

</deferred>

---

*Phase: 08-monitoring-verification-recovery*
*Context gathered: 2026-03-19*
