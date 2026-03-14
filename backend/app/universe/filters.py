from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import EligibilityDecision, EligibilityReason, UniverseCandidate, UniverseRules


class UniverseFilter:
    def __init__(self, rules: UniverseRules | None = None) -> None:
        self._rules = rules or UniverseRules()

    @property
    def rules(self) -> UniverseRules:
        return self._rules

    def evaluate(self, candidate: UniverseCandidate) -> EligibilityDecision:
        reasons: list[EligibilityReason] = []

        if not candidate.exchange or not candidate.instrument_type or candidate.is_common_stock is None:
            reasons.append(EligibilityReason.MISSING_METADATA)

        if candidate.exchange not in self._rules.allowed_exchanges:
            reasons.append(EligibilityReason.EXCHANGE_NOT_ALLOWED)

        if candidate.is_common_stock is not True:
            reasons.append(EligibilityReason.NOT_COMMON_STOCK)

        if candidate.instrument_type in self._rules.excluded_instrument_types:
            reasons.append(EligibilityReason.EXCLUDED_INSTRUMENT_TYPE)

        if candidate.last_price is None or not (self._rules.min_price <= candidate.last_price <= self._rules.max_price):
            reasons.append(EligibilityReason.PRICE_OUTSIDE_RANGE)

        if (
            candidate.average_daily_volume is None
            or candidate.average_daily_volume < self._rules.min_average_daily_volume
        ):
            reasons.append(EligibilityReason.ADV_BELOW_MINIMUM)

        unique_reasons = tuple(dict.fromkeys(reasons))
        return EligibilityDecision(candidate=candidate, eligible=not unique_reasons, reasons=unique_reasons)

    def filter(self, candidates: Iterable[UniverseCandidate]) -> tuple[UniverseCandidate, ...]:
        return tuple(
            decision.candidate
            for decision in (self.evaluate(candidate) for candidate in candidates)
            if decision.eligible
        )

    def decisions(self, candidates: Sequence[UniverseCandidate]) -> tuple[EligibilityDecision, ...]:
        return tuple(self.evaluate(candidate) for candidate in candidates)
