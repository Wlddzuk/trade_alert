from __future__ import annotations

from datetime import UTC, datetime

from app.ops.health_models import ProviderFreshnessRules
from app.ops.provider_health import ProviderHealthEvaluator
from app.providers.models import (
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
)
from app.runtime.session_window import RuntimeWindow


def _provider_snapshot(
    provider: str,
    capability: ProviderCapability,
    *,
    observed_at: datetime,
    freshness_age_seconds: float | None,
) -> ProviderHealthSnapshot:
    return ProviderHealthSnapshot(
        provider=provider,
        capability=capability,
        observed_at=observed_at,
        last_update_at=observed_at if freshness_age_seconds is not None else None,
        freshness_age_seconds=freshness_age_seconds,
        state=ProviderHealthState.HEALTHY,
        reason="test",
    )


def test_provider_health_uses_capability_specific_thresholds() -> None:
    evaluator = ProviderHealthEvaluator(ProviderFreshnessRules())
    runtime_state = RuntimeWindow().status_at(datetime(2026, 3, 13, 13, 45, tzinfo=UTC))

    market_status = evaluator.evaluate(
        _provider_snapshot(
            "polygon",
            ProviderCapability.MARKET_DATA,
            observed_at=runtime_state.observed_at_utc,
            freshness_age_seconds=20.0,
        ),
        runtime_state,
    )
    news_status = evaluator.evaluate(
        _provider_snapshot(
            "benzinga",
            ProviderCapability.NEWS,
            observed_at=runtime_state.observed_at_utc,
            freshness_age_seconds=20.0,
        ),
        runtime_state,
    )

    assert market_status.threshold_seconds == 15.0
    assert market_status.stale is True
    assert news_status.threshold_seconds == 60.0
    assert news_status.stale is False


def test_provider_health_ignores_staleness_outside_runtime_window() -> None:
    evaluator = ProviderHealthEvaluator()
    runtime_state = RuntimeWindow().status_at(datetime(2026, 3, 13, 7, 30, tzinfo=UTC))

    status = evaluator.evaluate(
        _provider_snapshot(
            "polygon",
            ProviderCapability.MARKET_DATA,
            observed_at=runtime_state.observed_at_utc,
            freshness_age_seconds=120.0,
        ),
        runtime_state,
    )

    assert status.within_runtime_window is False
    assert status.stale is False
    assert status.reason == "outside_runtime_window"
