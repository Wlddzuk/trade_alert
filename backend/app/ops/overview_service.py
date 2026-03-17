from __future__ import annotations

from .health_models import SystemTrustSnapshot, SystemTrustState
from .monitoring_models import (
    AlertDeliveryStatus,
    HealthSeverity,
    MonitoringStatus,
    ProviderFreshnessOverview,
    ScannerLoopHealth,
    StatusOverview,
)
from .system_events import SystemEvent


class OverviewService:
    def build_status_overview(
        self,
        snapshot: SystemTrustSnapshot,
        *,
        scanner_loop: ScannerLoopHealth,
        alert_delivery: AlertDeliveryStatus,
        recent_events: tuple[SystemEvent, ...] = (),
    ) -> StatusOverview:
        del recent_events

        runtime_state = snapshot.runtime_state
        if not runtime_state.scanning_active:
            status = MonitoringStatus.OFFLINE
            headline = "Session closed; monitoring is offline."
            scanner_status = self._offline_scanner_loop(scanner_loop)
        elif snapshot.trust_state is SystemTrustState.DEGRADED:
            status = MonitoringStatus.DEGRADED
            headline = "Monitoring degraded; actionable output remains blocked."
            scanner_status = scanner_loop
        elif snapshot.trust_state is SystemTrustState.RECOVERING:
            status = MonitoringStatus.RECOVERING
            headline = "Providers recovered; trust is still reconfirming."
            scanner_status = scanner_loop
        else:
            status = MonitoringStatus.HEALTHY
            headline = "Monitoring healthy and actionable."
            scanner_status = scanner_loop

        return StatusOverview(
            observed_at=snapshot.observed_at,
            status=status,
            actionable=snapshot.actionable,
            headline=headline,
            session_label=runtime_state.phase.value,
            trust_state=snapshot.trust_state,
            trust_reasons=snapshot.reasons,
            stale_context_visible=status in {MonitoringStatus.DEGRADED, MonitoringStatus.RECOVERING},
            provider_freshness=tuple(
                ProviderFreshnessOverview(
                    provider=status_snapshot.provider,
                    capability=status_snapshot.capability.value,
                    freshness_age_seconds=status_snapshot.snapshot.freshness_age_seconds,
                    threshold_seconds=status_snapshot.threshold_seconds,
                    stale=status_snapshot.stale,
                    status=self._provider_severity(status_snapshot.stale, runtime_state.scanning_active),
                    reason=status_snapshot.reason,
                )
                for status_snapshot in snapshot.provider_statuses
            ),
            scanner_loop=scanner_status,
            alert_delivery=alert_delivery,
        )

    def _offline_scanner_loop(self, scanner_loop: ScannerLoopHealth) -> ScannerLoopHealth:
        return ScannerLoopHealth(
            observed_at=scanner_loop.observed_at,
            last_iteration_at=scanner_loop.last_iteration_at,
            lag_seconds=scanner_loop.lag_seconds,
            status=HealthSeverity.OFFLINE,
            summary="Scanner idle outside the runtime window.",
        )

    def _provider_severity(self, stale: bool, scanning_active: bool) -> HealthSeverity:
        if not scanning_active:
            return HealthSeverity.OFFLINE
        if stale:
            return HealthSeverity.CRITICAL
        return HealthSeverity.HEALTHY
