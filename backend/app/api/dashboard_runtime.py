from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Callable

from app.audit.lifecycle_log import LifecycleLog
from app.audit.pnl_summary import PnlSummary, PnlSummaryService
from app.audit.review_models import TradeReviewFeed
from app.audit.review_service import TradeReviewService
from app.ops.alert_delivery_health import AlertDeliveryAttempt, AlertDeliveryHealthService
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.incident_log import IncidentLogReport, IncidentLogService
from app.ops.monitoring_models import AlertDeliverySnapshot, OperationsOverview, ScannerLoopSnapshot
from app.ops.overview_service import OperationsOverviewService
from app.ops.system_events import SystemEvent
from app.runtime.session_window import RuntimeWindow


@dataclass(frozen=True, slots=True)
class DashboardRuntimeSnapshot:
    overview: OperationsOverview
    incident_report: IncidentLogReport
    review_feed: TradeReviewFeed
    pnl_summary: PnlSummary
    last_updated_at: datetime
    refresh_interval_seconds: int = 30
    stale: bool = False
    stale_message: str | None = None


class DashboardRuntimeComposition:
    def __init__(
        self,
        *,
        trust_snapshot: SystemTrustSnapshot | None = None,
        system_events: tuple[SystemEvent, ...] = (),
        scanner_loop: ScannerLoopSnapshot | None = None,
        alert_delivery_attempts: tuple[AlertDeliveryAttempt, ...] = (),
        lifecycle_log: LifecycleLog | None = None,
        refresh_interval_seconds: int = 30,
    ) -> None:
        observed_at = datetime.now(UTC)
        runtime_state = RuntimeWindow().status_at(observed_at)
        self._trust_snapshot = trust_snapshot or SystemTrustSnapshot(
            observed_at=observed_at,
            trust_state=SystemTrustState.HEALTHY,
            actionable=runtime_state.scanning_active,
            runtime_state=runtime_state,
            provider_statuses=(),
            reasons=(),
        )
        self._system_events = list(system_events)
        self._scanner_loop = scanner_loop
        self._alert_delivery_attempts = list(alert_delivery_attempts)
        self._lifecycle_log = lifecycle_log or LifecycleLog()
        self._refresh_interval_seconds = refresh_interval_seconds
        self._overview_service = OperationsOverviewService()
        self._incident_log_service = IncidentLogService()
        self._review_service = TradeReviewService()
        self._pnl_summary_service = PnlSummaryService(review_service=self._review_service)
        self._alert_delivery_health_service = AlertDeliveryHealthService()

    @property
    def lifecycle_log(self) -> LifecycleLog:
        return self._lifecycle_log

    def replace_trust_snapshot(self, snapshot: SystemTrustSnapshot) -> None:
        self._trust_snapshot = snapshot

    def set_scanner_loop(self, snapshot: ScannerLoopSnapshot | None) -> None:
        self._scanner_loop = snapshot

    def replace_system_events(self, events: tuple[SystemEvent, ...]) -> None:
        self._system_events = list(events)

    def record_system_event(self, event: SystemEvent) -> None:
        self._system_events.append(event)

    def replace_alert_delivery_attempts(self, attempts: tuple[AlertDeliveryAttempt, ...]) -> None:
        self._alert_delivery_attempts = list(attempts)

    def record_alert_delivery_attempt(self, attempt: AlertDeliveryAttempt) -> None:
        self._alert_delivery_attempts.append(attempt)

    def record_alert_delivery_attempts(self, attempts: tuple[AlertDeliveryAttempt, ...]) -> None:
        self._alert_delivery_attempts.extend(attempts)

    def snapshot_provider(self) -> "DashboardRuntimeSnapshotProvider":
        return DashboardRuntimeSnapshotProvider(snapshot_factory=self.build_snapshot)

    def build_snapshot(self) -> DashboardRuntimeSnapshot:
        observed_at = self._trust_snapshot.observed_at
        attempts = tuple(self._alert_delivery_attempts)
        delivery_report = None
        alert_delivery_snapshot: AlertDeliverySnapshot | None = None
        if attempts:
            delivery_report = self._alert_delivery_health_service.build_report(
                attempts,
                observed_at=observed_at,
            )
            alert_delivery_snapshot = AlertDeliverySnapshot(
                observed_at=observed_at,
                last_attempt_at=delivery_report.snapshot.last_attempt_at,
                last_success_at=delivery_report.snapshot.last_success_at,
                consecutive_failures=delivery_report.snapshot.consecutive_failures,
                last_failure_reason=(
                    delivery_report.recent_failures[0].reason if delivery_report.recent_failures else None
                ),
            )

        events = self._lifecycle_log.all_events()
        return DashboardRuntimeSnapshot(
            overview=self._overview_service.build_overview(
                self._trust_snapshot,
                scanner_loop=self._scanner_loop,
                alert_delivery=alert_delivery_snapshot,
            ),
            incident_report=self._incident_log_service.build(
                tuple(self._system_events),
                delivery_report=delivery_report,
            ),
            review_feed=self._review_service.build_completed_trade_feed(events),
            pnl_summary=self._pnl_summary_service.build(events, today=observed_at),
            last_updated_at=observed_at,
            refresh_interval_seconds=self._refresh_interval_seconds,
        )


class DashboardRuntimeSnapshotProvider:
    def __init__(
        self,
        *,
        snapshot_factory: Callable[[], DashboardRuntimeSnapshot] | None = None,
    ) -> None:
        self._snapshot_factory = snapshot_factory or create_default_dashboard_runtime().build_snapshot
        self._last_successful_snapshot: DashboardRuntimeSnapshot | None = None

    def build_snapshot(self) -> DashboardRuntimeSnapshot:
        try:
            snapshot = self._snapshot_factory()
        except Exception:
            if self._last_successful_snapshot is None:
                raise
            return replace(
                self._last_successful_snapshot,
                stale=True,
                stale_message="Showing the last successful snapshot while runtime refresh is unavailable.",
            )
        self._last_successful_snapshot = snapshot
        return snapshot


_DEFAULT_DASHBOARD_RUNTIME: DashboardRuntimeComposition | None = None


def create_default_dashboard_runtime() -> DashboardRuntimeComposition:
    global _DEFAULT_DASHBOARD_RUNTIME
    if _DEFAULT_DASHBOARD_RUNTIME is None:
        _DEFAULT_DASHBOARD_RUNTIME = DashboardRuntimeComposition()
    return _DEFAULT_DASHBOARD_RUNTIME


def reset_default_dashboard_runtime() -> DashboardRuntimeComposition:
    global _DEFAULT_DASHBOARD_RUNTIME
    _DEFAULT_DASHBOARD_RUNTIME = DashboardRuntimeComposition()
    return _DEFAULT_DASHBOARD_RUNTIME
