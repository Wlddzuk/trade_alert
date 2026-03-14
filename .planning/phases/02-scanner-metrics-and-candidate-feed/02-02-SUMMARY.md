---
phase: 02-scanner-metrics-and-candidate-feed
plan: 02
subsystem: scanner
tags: [python, scanner, news-linking, rows, pytest]
requires:
  - phase: 02-scanner-metrics-and-candidate-feed
    provides: normalized market metrics and baseline history inputs
provides:
  - symbol-centric news linking with latest-headline semantics
  - candidate row models exposing the required Phase 2 scanner fields
  - deterministic row-assembly tests for required-field gating and why-surfaced output
affects: [phase-02, phase-03, phase-04]
tech-stack:
  added: []
  patterns: [symbol-centric-latest-headline-linking, required-field-gating, deterministic-why-surfaced]
key-files:
  created:
    - backend/app/scanner/models.py
    - backend/app/scanner/news_linking.py
    - backend/app/scanner/row_builder.py
    - backend/tests/scanner_feed/test_candidate_rows.py
  modified: []
key-decisions:
  - "One live row per symbol was preserved by resolving multiple related headlines into one latest-headline view instead of duplicating rows per catalyst event."
  - "The displayed catalyst tag and time-since-news value follow the latest displayed headline so the row stays internally consistent."
  - "Rows are withheld until the core Phase 2 fields are present, avoiding partially usable rows in the live feed."
patterns-established:
  - "Latest related news is linked per symbol before row assembly begins."
  - "Candidate rows are immutable scanner records that can later be decorated by Phase 3 validity and ranking logic."
  - "Why-surfaced text is deterministic and built from currently available scanner context."
requirements-completed: [DATA-05, SCAN-01, SCAN-04]
duration: 2 min
completed: 2026-03-14
---

# Phase 2: Scanner Metrics and Candidate Feed Summary

**Symbol-centric candidate rows with latest-headline semantics, catalyst tags, time-since-news context, and required scanner fields**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T19:14:01Z
- **Completed:** 2026-03-14T19:15:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented symbol-centric news linking so one current row can represent multiple related headline updates without creating duplicate feed entries.
- Added the immutable candidate-row model and row builder for the required Phase 2 scanner columns, including headline, catalyst tag, time since news, move context, RVOL context, and pullback % from high of day.
- Added deterministic tests for latest-headline resolution, row-field completeness, and why-surfaced output.

## Task Commits

1. **Task 1 and Task 2: Implement latest-headline linking and candidate row assembly** - `1937069` (feat)

## Files Created/Modified

- `backend/app/scanner/models.py` - linked-news and candidate-row contracts used by downstream feed state
- `backend/app/scanner/news_linking.py` - latest-headline resolution for one current symbol view
- `backend/app/scanner/row_builder.py` - required-field gating plus candidate-row assembly and why-surfaced generation
- `backend/tests/scanner_feed/test_candidate_rows.py` - coverage for symbol-centric news linking and row assembly

## Decisions & Deviations

- Preserved a single live row per symbol because the operator feed is meant to track current movers, not build a per-headline audit stream.
- Kept the row builder strategy-light so `setup_valid`, invalidations, and formal score/rank remain a Phase 3 concern.
- There was one execution deviation: both planned tasks landed in a single commit because the row model, latest-headline semantics, and row builder were tightly coupled and cleaner to verify together.

## Next Phase Readiness

- Plan `02-03` can use a stable symbol-keyed row identity without inventing its own feed identity rules.
- Phase 3 can decorate candidate rows with `setup_valid`, invalidation reasons, and score/rank without replacing the row contract.
- No blockers remain for the final Phase 2 feed-state plan.
