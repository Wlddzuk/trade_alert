from __future__ import annotations

from datetime import UTC, datetime

from app.ops.degraded_state import SystemTrustMonitor
from app.ops.health_models import ProviderFreshnessRules, SystemTrustState
from app.ops.provider_health import ProviderHealthEvaluator
from app.ops.system_events import SystemEventType
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


def _provider_status(
    provider: str,
    capability: ProviderCapability,
    *,
    runtime_at: datetime,
    freshness_age_seconds: float | None,
):
    runtime_state = RuntimeWindow().status_at(runtime_at)
    evaluator = ProviderHealthEvaluator()
    return evaluator.evaluate(
        _provider_snapshot(
            provider,
            capability,
            observed_at=runtime_state.observed_at_utc,
            freshness_age_seconds=freshness_age_seconds,
        ),
        runtime_state,
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


def test_system_trust_degrades_when_any_provider_is_stale_during_runtime() -> None:
    runtime_at = datetime(2026, 3, 13, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    monitor = SystemTrustMonitor()

    transition = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=5.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=75.0,
            ),
        ),
        runtime_state,
    )

    assert transition.snapshot.trust_state is SystemTrustState.DEGRADED
    assert transition.snapshot.actionable is False
    assert transition.snapshot.reasons == ("benzinga:news:stale_provider_update",)
    assert transition.events[0].event_type == SystemEventType.PROVIDER_TRUST_DEGRADED


def test_system_trust_does_not_degrade_outside_runtime_window() -> None:
    runtime_at = datetime(2026, 3, 13, 7, 30, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    monitor = SystemTrustMonitor()

    transition = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=120.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=120.0,
            ),
        ),
        runtime_state,
        previous_state=SystemTrustState.DEGRADED,
    )

    assert transition.snapshot.trust_state is SystemTrustState.HEALTHY
    assert transition.snapshot.actionable is False
    assert transition.snapshot.reasons == ("outside_runtime_window",)
    assert transition.events == ()


def test_system_trust_transitions_from_degraded_to_recovering_to_healthy() -> None:
    runtime_at = datetime(2026, 3, 13, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    monitor = SystemTrustMonitor()

    degraded = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=20.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=30.0,
            ),
        ),
        runtime_state,
    )
    recovering = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=5.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=10.0,
            ),
        ),
        runtime_state,
        previous_state=degraded.snapshot.trust_state,
    )
    healthy = monitor.evaluate(
        recovering.snapshot.provider_statuses,
        runtime_state,
        previous_state=recovering.snapshot.trust_state,
    )

    assert degraded.snapshot.trust_state is SystemTrustState.DEGRADED
    assert recovering.snapshot.trust_state is SystemTrustState.RECOVERING
    assert recovering.snapshot.actionable is False
    assert recovering.events[0].event_type == SystemEventType.PROVIDER_TRUST_RECOVERING
    assert healthy.snapshot.trust_state is SystemTrustState.HEALTHY
    assert healthy.snapshot.actionable is True
    assert healthy.events[0].event_type == SystemEventType.PROVIDER_TRUST_RESTORED


def test_actionable_trust_stays_blocked_until_both_providers_recover() -> None:
    runtime_at = datetime(2026, 3, 13, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    monitor = SystemTrustMonitor()

    still_degraded = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=5.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=75.0,
            ),
        ),
        runtime_state,
        previous_state=SystemTrustState.DEGRADED,
    )
    recovering = monitor.evaluate(
        (
            _provider_status(
                "polygon",
                ProviderCapability.MARKET_DATA,
                runtime_at=runtime_at,
                freshness_age_seconds=5.0,
            ),
            _provider_status(
                "benzinga",
                ProviderCapability.NEWS,
                runtime_at=runtime_at,
                freshness_age_seconds=10.0,
            ),
        ),
        runtime_state,
        previous_state=still_degraded.snapshot.trust_state,
    )

    assert still_degraded.snapshot.trust_state is SystemTrustState.DEGRADED
    assert still_degraded.snapshot.actionable is False
    assert recovering.snapshot.trust_state is SystemTrustState.RECOVERING
    assert recovering.snapshot.actionable is False
