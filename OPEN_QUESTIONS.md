# Open Questions: Buy Signal MVP

**Date:** 2026-03-12
**Purpose:** Capture only the decisions that are still unresolved before implementation planning.

## 1. How should score/rank be computed in v1?

Still needed:

- Which factors drive rank most strongly
- Whether the score is rule-based, weighted, or tiered
- Whether operator-facing score output should be numeric, bucketed, or both

Why it matters:

- Ranking determines what the operator sees first and how much trust the scanner earns.

## 2. How should the remaining soft trade-quality rules become explicit?

Still needed:

- Definition of `broken momentum`
- Definition of `key intraday trend context`
- Definition of `signal arrives too late in the move`
- Definition of `repeated failed breakouts`
- Definition of `live volume appears abnormally thin at trigger time`

Why it matters:

- These need measurable rule definitions before implementation details can be finalized cleanly.
