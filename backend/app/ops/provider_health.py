from __future__ import annotations

from app.providers.models import ProviderHealthSnapshot
from app.runtime.session_window import RuntimeWindowState

from .health_models import ProviderFreshnessRules, ProviderFreshnessStatus


class ProviderHealthEvaluator:
    def __init__(self, rules: ProviderFreshnessRules | None = None) -> None:
        self._rules = rules or ProviderFreshnessRules()

    @property
    def rules(self) -> ProviderFreshnessRules:
        return self._rules

    def evaluate(
        self,
        snapshot: ProviderHealthSnapshot,
        runtime_state: RuntimeWindowState,
    ) -> ProviderFreshnessStatus:
        threshold = self._rules.threshold_for(snapshot.capability)

        if not runtime_state.scanning_active:
            return ProviderFreshnessStatus(
                provider=snapshot.provider,
                capability=snapshot.capability,
                observed_at=runtime_state.observed_at_utc,
                threshold_seconds=threshold,
                stale=False,
                within_runtime_window=False,
                reason="outside_runtime_window",
                snapshot=snapshot,
            )

        freshness_age = snapshot.freshness_age_seconds
        stale = freshness_age is None or freshness_age > threshold
        reason = "stale_provider_update" if stale else "within_freshness_threshold"
        return ProviderFreshnessStatus(
            provider=snapshot.provider,
            capability=snapshot.capability,
            observed_at=runtime_state.observed_at_utc,
            threshold_seconds=threshold,
            stale=stale,
            within_runtime_window=True,
            reason=reason,
            snapshot=snapshot,
        )
