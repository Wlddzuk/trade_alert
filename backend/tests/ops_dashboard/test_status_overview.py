from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ops.health_models import ProviderFreshnessRules, SystemTrustState
from app.ops.monitoring_models import AlertDeliveryStatus, HealthSeverity, MonitoringStatus, ScannerLoopHealth
from app.ops.overview_service import OverviewService
from app.ops.provider_health import ProviderHealthEvaluator
from app.providers.models import ProviderCapability, ProviderHealthSnapshot, ProviderHealthState
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
        last_update_at=None if freshness_age_seconds is None else observed_at - timedelta(seconds=freshness_age_seconds),
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
    evaluator = ProviderHealthEvaluator(ProviderFreshnessRules())
    return evaluator.evaluate(
        _provider_snapshot(
            provider,
            capability,
            observed_at=runtime_state.observed_at_utc,
            freshness_age_seconds=freshness_age_seconds,
        ),
        runtime_state,
    )


def _scanner_loop(runtime_at: datetime, *, status: HealthSeverity, lag_seconds: float, summary: str) -> ScannerLoopHealth:
    return ScannerLoopHealth(
        observed_at=runtime_at,
        last_iteration_at=runtime_at - timedelta(seconds=lag_seconds),
        lag_seconds=lag_seconds,
        status=status,
        summary=summary,
    )


def _alert_delivery(runtime_at: datetime, *, status: HealthSeverity, summary: str, failures: int = 0) -> AlertDeliveryStatus:
    return AlertDeliveryStatus(
        observed_at=runtime_at,
        status=status,
        summary=summary,
        consecutive_failures=failures,
        last_attempt_at=runtime_at,
        last_success_at=None if failures else runtime_at - timedelta(seconds=5),
    )


def test_status_overview_distinguishes_healthy_degraded_and_recovering() -> None:
    runtime_at = datetime(2026, 3, 17, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    service = OverviewService()

    healthy_snapshot = _build_snapshot(
        runtime_at,
        provider_statuses=(
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=5.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=15.0),
        ),
        trust_state=SystemTrustState.HEALTHY,
        actionable=True,
        reasons=("all_providers_fresh",),
    )
    degraded_snapshot = _build_snapshot(
        runtime_at,
        provider_statuses=(
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=30.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=15.0),
        ),
        trust_state=SystemTrustState.DEGRADED,
        actionable=False,
        reasons=("polygon:market_data:stale_provider_update",),
    )
    recovering_snapshot = _build_snapshot(
        runtime_at,
        provider_statuses=healthy_snapshot.provider_statuses,
        trust_state=SystemTrustState.RECOVERING,
        actionable=False,
        reasons=("providers_recovered_waiting_confirmation",),
    )

    healthy = service.build_status_overview(
        healthy_snapshot,
        scanner_loop=_scanner_loop(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, lag_seconds=8.0, summary="Scanner loop healthy."),
        alert_delivery=_alert_delivery(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, summary="Telegram delivery healthy."),
    )
    degraded = service.build_status_overview(
        degraded_snapshot,
        scanner_loop=_scanner_loop(runtime_state.observed_at_utc, status=HealthSeverity.WARNING, lag_seconds=22.0, summary="Scanner loop delayed."),
        alert_delivery=_alert_delivery(runtime_state.observed_at_utc, status=HealthSeverity.WARNING, summary="Recent Telegram delivery failures.", failures=2),
    )
    recovering = service.build_status_overview(
        recovering_snapshot,
        scanner_loop=_scanner_loop(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, lag_seconds=9.0, summary="Scanner loop healthy."),
        alert_delivery=_alert_delivery(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, summary="Telegram delivery healthy."),
    )

    assert healthy.status is MonitoringStatus.HEALTHY
    assert healthy.actionable is True
    assert healthy.stale_context_visible is False
    assert degraded.status is MonitoringStatus.DEGRADED
    assert degraded.actionable is False
    assert degraded.stale_context_visible is True
    assert degraded.provider_freshness[0].status is HealthSeverity.CRITICAL
    assert recovering.status is MonitoringStatus.RECOVERING
    assert recovering.actionable is False
    assert recovering.stale_context_visible is True


def test_status_overview_uses_neutral_offline_state_outside_runtime_window() -> None:
    runtime_at = datetime(2026, 3, 17, 1, 15, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    service = OverviewService()
    snapshot = _build_snapshot(
        runtime_at,
        provider_statuses=(
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=240.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=240.0),
        ),
        trust_state=SystemTrustState.HEALTHY,
        actionable=False,
        reasons=("outside_runtime_window",),
    )

    overview = service.build_status_overview(
        snapshot,
        scanner_loop=_scanner_loop(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, lag_seconds=600.0, summary="Loop not relevant while offline."),
        alert_delivery=_alert_delivery(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, summary="No delivery issues."),
    )

    assert overview.status is MonitoringStatus.OFFLINE
    assert overview.actionable is False
    assert overview.session_label == "offline"
    assert overview.headline == "Session closed; monitoring is offline."
    assert overview.stale_context_visible is False
    assert overview.scanner_loop.status is HealthSeverity.OFFLINE
    assert all(provider.status is HealthSeverity.OFFLINE for provider in overview.provider_freshness)


def test_status_overview_surfaces_provider_freshness_scanner_loop_and_delivery_health() -> None:
    runtime_at = datetime(2026, 3, 17, 14, 10, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    service = OverviewService()
    snapshot = _build_snapshot(
        runtime_at,
        provider_statuses=(
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=12.5),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=48.0),
        ),
        trust_state=SystemTrustState.HEALTHY,
        actionable=True,
        reasons=("all_providers_fresh",),
    )

    overview = service.build_status_overview(
        snapshot,
        scanner_loop=_scanner_loop(runtime_state.observed_at_utc, status=HealthSeverity.HEALTHY, lag_seconds=11.0, summary="Scanner loop healthy."),
        alert_delivery=_alert_delivery(runtime_state.observed_at_utc, status=HealthSeverity.WARNING, summary="2 recent delivery failures.", failures=2),
    )

    assert [item.provider for item in overview.provider_freshness] == ["polygon", "benzinga"]
    assert overview.provider_freshness[0].freshness_age_seconds == 12.5
    assert overview.provider_freshness[1].threshold_seconds == 60.0
    assert overview.scanner_loop.summary == "Scanner loop healthy."
    assert overview.scanner_loop.lag_seconds == 11.0
    assert overview.alert_delivery.consecutive_failures == 2
    assert overview.alert_delivery.summary == "2 recent delivery failures."


def _build_snapshot(
    observed_at: datetime,
    *,
    provider_statuses: tuple,
    trust_state: SystemTrustState,
    actionable: bool,
    reasons: tuple[str, ...],
):
    runtime_state = RuntimeWindow().status_at(observed_at)
    from app.ops.health_models import SystemTrustSnapshot

    return SystemTrustSnapshot(
        observed_at=runtime_state.observed_at_utc,
        trust_state=trust_state,
        actionable=actionable,
        runtime_state=runtime_state,
        provider_statuses=provider_statuses,
        reasons=reasons,
    )
