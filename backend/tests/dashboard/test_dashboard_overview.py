from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.api.dashboard_routes import DashboardRoutes
from app.ops.degraded_state import SystemTrustMonitor
from app.ops.health_models import ProviderFreshnessRules, SystemTrustState
from app.ops.incident_log import IncidentLogService
from app.ops.monitoring_models import AlertDeliverySnapshot, ScannerLoopSnapshot
from app.ops.overview_service import OperationsOverviewService
from app.ops.provider_health import ProviderHealthEvaluator
from app.ops.system_events import SystemEvent, SystemEventType
from app.providers.models import ProviderCapability, ProviderHealthSnapshot, ProviderHealthState
from app.runtime.session_window import RuntimeWindow


def _provider_status(
    provider: str,
    capability: ProviderCapability,
    *,
    runtime_at: datetime,
    freshness_age_seconds: float,
):
    runtime_state = RuntimeWindow().status_at(runtime_at)
    evaluator = ProviderHealthEvaluator(ProviderFreshnessRules())
    return evaluator.evaluate(
        ProviderHealthSnapshot(
            provider=provider,
            capability=capability,
            observed_at=runtime_state.observed_at_utc,
            last_update_at=runtime_state.observed_at_utc - timedelta(seconds=freshness_age_seconds),
            freshness_age_seconds=freshness_age_seconds,
            state=ProviderHealthState.HEALTHY,
            reason="test",
        ),
        runtime_state,
    )


def test_dashboard_overview_renders_read_only_status_first_surface() -> None:
    runtime_at = datetime(2026, 3, 17, 13, 45, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    transition = SystemTrustMonitor().evaluate(
        (
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=20.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=12.0),
        ),
        runtime_state,
    )
    overview = OperationsOverviewService().build_overview(
        transition.snapshot,
        scanner_loop=ScannerLoopSnapshot(observed_at=runtime_at, last_success_at=runtime_at - timedelta(seconds=25)),
        alert_delivery=AlertDeliverySnapshot(
            observed_at=runtime_at,
            last_attempt_at=runtime_at - timedelta(seconds=3),
            last_success_at=runtime_at - timedelta(minutes=2),
            consecutive_failures=2,
            last_failure_reason="telegram_timeout",
        ),
    )
    incident_report = IncidentLogService().build(
        (
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                observed_at=runtime_at,
                trust_state=SystemTrustState.DEGRADED,
                actionable=False,
                reasons=("polygon:market_data:stale_provider_update",),
            ),
        )
    )

    html = DashboardRoutes().render_overview_page(overview, incident_report)

    assert "Read-only dashboard" in html
    assert "Telegram remains the primary workflow." in html
    assert "Status Overview" in html
    assert "degraded" in html
    assert "Recent critical issues: 1" in html
    assert "<button" not in html
    assert "<form" not in html


def test_dashboard_overview_distinguishes_offline_session_closed() -> None:
    runtime_at = datetime(2026, 3, 17, 1, 15, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(runtime_at)
    transition = SystemTrustMonitor().evaluate(
        (
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=500.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=500.0),
        ),
        runtime_state,
        previous_state=SystemTrustState.DEGRADED,
    )
    overview = OperationsOverviewService().build_overview(transition.snapshot)
    incident_report = IncidentLogService().build(())

    html = DashboardRoutes().render_overview_page(overview, incident_report)

    assert "offline_session_closed" in html
    assert "Session closed. Monitoring idle during offline." in html
