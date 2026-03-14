from __future__ import annotations

from collections.abc import Iterable

from .filters import UniverseFilter
from .models import EligibilityDecision, UniverseCandidate


class UniverseReferenceData:
    def __init__(self, candidates: Iterable[UniverseCandidate]) -> None:
        self._candidates = {candidate.symbol: candidate for candidate in candidates}

    def get(self, symbol: str) -> UniverseCandidate | None:
        return self._candidates.get(symbol.strip().upper())

    def all_candidates(self) -> tuple[UniverseCandidate, ...]:
        return tuple(self._candidates.values())

    def eligibility(self, universe_filter: UniverseFilter) -> tuple[EligibilityDecision, ...]:
        return universe_filter.decisions(self.all_candidates())

    def eligible_candidates(self, universe_filter: UniverseFilter) -> tuple[UniverseCandidate, ...]:
        return universe_filter.filter(self.all_candidates())
