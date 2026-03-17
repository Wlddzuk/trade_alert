from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ops.degraded_state import SystemTrustMonitor
from app.ops.health_models import ProviderFreshnessRules, SystemTrustState
from app.ops.monitoring_models import (
    AlertDeliverySnapshot,
    AlertDeliveryState,
    OperationsStatus,
    ScannerLoopSnapshot,
    ScannerLoopState,
)
from app.ops.overview_service import OperationsOverviewService
from app.ops.provider_health import ProviderHealthEvaluator
from app.ops.system_events import SystemEventType
from app.providers.models import ProviderCapability, ProviderHealthSnapshot, ProviderHealthState
from app.runtime.session_window import RuntimeWindow


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
        ProviderHealthSnapshot(
            provider=provider,
            capability=capability,
            observed_at=runtime_state.observed_at_utc,
            last_update_at=None
            if freshness_age_seconds is None
            else runtime_state.observed_at_utc - timedelta(seconds=freshness_age_seconds),
            freshness_age_seconds=freshness_age_seconds,
            state=ProviderHealthState.HEALTHY,
            reason="test",
        ),
        runtime_state,
    )


def test_status_overview_reports_healthy_runtime_with_explicit_health_sections() -> None:
    runtime_at = datetime(2026, 3, 17, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    provider_statuses = (
        _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=5.0),
        _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=10.0),
    )
    service = OperationsOverviewService()

    transition = service.build_overview(
        trust_snapshot=SystemTrustMonitor().evaluate(
            provider_statuses,
            runtime_state,
        ).snapshot,
        scanner_loop=ScannerLoopSnapshot(
            observed_at=runtime_at,
            last_success_at=runtime_at - timedelta(seconds=20),
        ),
        alert_delivery=AlertDeliverySnapshot(
            observed_at=runtime_at,
            last_attempt_at=runtime_at - timedelta(seconds=5),
            last_success_at=runtime_at - timedelta(seconds=5),
            consecutive_failures=0,
        ),
    )

    assert transition.status is OperationsStatus.HEALTHY
    assert transition.actionable is True
    assert transition.scanner_loop.state is ScannerLoopState.RUNNING
    assert transition.alert_delivery.state is AlertDeliveryState.HEALTHY
    assert tuple(view.status for view in transition.provider_freshness) == ("fresh", "fresh")
    assert transition.headline == "System healthy. Monitoring is actionable."


def test_status_overview_reports_degraded_and_recovering_trust_distinctly() -> None:
    runtime_at = datetime(2026, 3, 17, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    service = OperationsOverviewService()
    monitor = SystemTrustMonitor()

    degraded = monitor.evaluate(
        (
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=25.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=10.0),
        ),
        runtime_state,
    )
    recovering = monitor.evaluate(
        (
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=5.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=10.0),
        ),
        runtime_state,
        previous_state=degraded.snapshot.trust_state,
    )

    degraded_view = service.build_overview(
        degraded.snapshot,
        scanner_loop=ScannerLoopSnapshot(
            observed_at=runtime_at,
            last_success_at=runtime_at - timedelta(seconds=95),
            last_error="loop_timeout",
        ),
        alert_delivery=AlertDeliverySnapshot(
            observed_at=runtime_at,
            last_attempt_at=runtime_at - timedelta(seconds=8),
            last_success_at=runtime_at - timedelta(minutes=2),
            consecutive_failures=2,
            last_failure_reason="telegram_timeout",
        ),
    )
    recovering_view = service.build_overview(
        recovering.snapshot,
        scanner_loop=ScannerLoopSnapshot(
            observed_at=runtime_at,
            last_success_at=runtime_at - timedelta(seconds=30),
        ),
    )

    assert degraded.events[0].event_type is SystemEventType.PROVIDER_TRUST_DEGRADED
    assert degraded_view.status is OperationsStatus.DEGRADED
    assert degraded_view.actionable is False
    assert degraded_view.scanner_loop.state is ScannerLoopState.STALE
    assert degraded_view.alert_delivery.state is AlertDeliveryState.DEGRADED
    assert degraded_view.trust_reasons == ("polygon:market_data:stale_provider_update",)

    assert recovering.snapshot.trust_state is SystemTrustState.RECOVERING
    assert recovering.events[0].event_type is SystemEventType.PROVIDER_TRUST_RECOVERING
    assert recovering_view.status is OperationsStatus.RECOVERING
    assert recovering_view.actionable is False
    assert recovering_view.headline == "Providers recovered. Monitoring remains in confirmation mode."


def test_status_overview_reports_offline_session_closed_neutrally() -> None:
    runtime_at = datetime(2026, 3, 17, 1, 15, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    provider_statuses = (
        _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=500.0),
        _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=500.0),
    )
    monitor = SystemTrustMonitor()
    service = OperationsOverviewService()

    overview = service.build_overview(
        monitor.evaluate(
            provider_statuses,
            runtime_state,
            previous_state=SystemTrustState.DEGRADED,
        ).snapshot,
    )

    assert overview.status is OperationsStatus.OFFLINE
    assert overview.actionable is False
    assert overview.scanner_loop.state is ScannerLoopState.IDLE
    assert overview.alert_delivery.state is AlertDeliveryState.OFFLINE
    assert overview.trust_reasons == ("outside_runtime_window",)
    assert overview.headline == "Session closed. Monitoring idle during offline."
