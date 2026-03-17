from __future__ import annotations

from app.ops.health_models import SystemTrustSnapshot, SystemTrustState

from .monitoring_models import (
    AlertDeliveryHealth,
    AlertDeliverySnapshot,
    AlertDeliveryState,
    OperationsOverview,
    OperationsStatus,
    ScannerLoopHealth,
    ScannerLoopSnapshot,
    ScannerLoopState,
    build_provider_freshness_views,
)


class OperationsOverviewService:
    def build_overview(
        self,
        trust_snapshot: SystemTrustSnapshot,
        *,
        scanner_loop: ScannerLoopSnapshot | None = None,
        alert_delivery: AlertDeliverySnapshot | None = None,
    ) -> OperationsOverview:
        status = self._status_from_snapshot(trust_snapshot)
        return OperationsOverview(
            observed_at=trust_snapshot.observed_at,
            status=status,
            headline=self._headline_for(status),
            actionable=trust_snapshot.actionable,
            runtime_phase=trust_snapshot.runtime_state.phase,
            provider_freshness=build_provider_freshness_views(trust_snapshot.provider_statuses),
            scanner_loop=self._build_scanner_loop_health(scanner_loop, trust_snapshot),
            alert_delivery=self._build_alert_delivery_health(alert_delivery, trust_snapshot),
            trust_reasons=trust_snapshot.reasons,
        )

    def _status_from_snapshot(self, snapshot: SystemTrustSnapshot) -> OperationsStatus:
        if not snapshot.runtime_state.scanning_active:
            return OperationsStatus.OFFLINE
        if snapshot.trust_state is SystemTrustState.DEGRADED:
            return OperationsStatus.DEGRADED
        if snapshot.trust_state is SystemTrustState.RECOVERING:
            return OperationsStatus.RECOVERING
        return OperationsStatus.HEALTHY

    def _headline_for(self, status: OperationsStatus) -> str:
        if status is OperationsStatus.OFFLINE:
            return "Session closed. Monitoring idle during offline."
        if status is OperationsStatus.DEGRADED:
            return "Degraded trust. Monitoring is visible but actionability stays blocked."
        if status is OperationsStatus.RECOVERING:
            return "Providers recovered. Monitoring remains in confirmation mode."
        return "System healthy. Monitoring is actionable."

    def _build_scanner_loop_health(
        self,
        snapshot: ScannerLoopSnapshot | None,
        trust_snapshot: SystemTrustSnapshot,
    ) -> ScannerLoopHealth:
        if not trust_snapshot.runtime_state.scanning_active:
            return ScannerLoopHealth(
                state=ScannerLoopState.IDLE,
                summary="Scanner loop idle outside the runtime window.",
                last_success_at=None if snapshot is None else snapshot.last_success_at,
                idle_seconds=None,
                last_error=None if snapshot is None else snapshot.last_error,
            )
        if snapshot is None or snapshot.last_success_at is None:
            return ScannerLoopHealth(
                state=ScannerLoopState.STALE,
                summary="Scanner loop heartbeat missing during the active session.",
                last_success_at=None,
                idle_seconds=None,
                last_error=None if snapshot is None else snapshot.last_error,
            )

        idle_seconds = (trust_snapshot.observed_at - snapshot.last_success_at).total_seconds()
        if idle_seconds > snapshot.max_idle_seconds:
            return ScannerLoopHealth(
                state=ScannerLoopState.STALE,
                summary="Scanner loop heartbeat is stale.",
                last_success_at=snapshot.last_success_at,
                idle_seconds=idle_seconds,
                last_error=snapshot.last_error,
            )
        return ScannerLoopHealth(
            state=ScannerLoopState.RUNNING,
            summary="Scanner loop heartbeat is healthy.",
            last_success_at=snapshot.last_success_at,
            idle_seconds=idle_seconds,
            last_error=snapshot.last_error,
        )

    def _build_alert_delivery_health(
        self,
        snapshot: AlertDeliverySnapshot | None,
        trust_snapshot: SystemTrustSnapshot,
    ) -> AlertDeliveryHealth:
        if not trust_snapshot.runtime_state.scanning_active:
            return AlertDeliveryHealth(
                state=AlertDeliveryState.OFFLINE,
                summary="Alert delivery idle outside the runtime window.",
                consecutive_failures=0 if snapshot is None else snapshot.consecutive_failures,
                last_attempt_at=None if snapshot is None else snapshot.last_attempt_at,
                last_success_at=None if snapshot is None else snapshot.last_success_at,
                last_failure_reason=None if snapshot is None else snapshot.last_failure_reason,
            )
        if snapshot is None or snapshot.consecutive_failures == 0:
            return AlertDeliveryHealth(
                state=AlertDeliveryState.HEALTHY,
                summary="Alert delivery healthy.",
                consecutive_failures=0 if snapshot is None else snapshot.consecutive_failures,
                last_attempt_at=None if snapshot is None else snapshot.last_attempt_at,
                last_success_at=None if snapshot is None else snapshot.last_success_at,
                last_failure_reason=None if snapshot is None else snapshot.last_failure_reason,
            )
        return AlertDeliveryHealth(
            state=AlertDeliveryState.DEGRADED,
            summary="Alert delivery failures detected.",
            consecutive_failures=snapshot.consecutive_failures,
            last_attempt_at=snapshot.last_attempt_at,
            last_success_at=snapshot.last_success_at,
            last_failure_reason=snapshot.last_failure_reason,
        )
