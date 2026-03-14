from __future__ import annotations

from dataclasses import dataclass

from app.runtime.session_window import RuntimeWindowState

from .health_models import ProviderFreshnessStatus, SystemTrustSnapshot, SystemTrustState
from .system_events import SystemEvent, SystemEventType


@dataclass(frozen=True, slots=True)
class SystemTrustTransition:
    previous_state: SystemTrustState | None
    snapshot: SystemTrustSnapshot
    events: tuple[SystemEvent, ...]


class SystemTrustMonitor:
    def evaluate(
        self,
        provider_statuses: tuple[ProviderFreshnessStatus, ...],
        runtime_state: RuntimeWindowState,
        *,
        previous_state: SystemTrustState | None = None,
    ) -> SystemTrustTransition:
        statuses = tuple(provider_statuses)
        if not statuses:
            raise ValueError("provider_statuses must not be empty")

        next_state, actionable, reasons = self._derive_state(statuses, runtime_state, previous_state)
        snapshot = SystemTrustSnapshot(
            observed_at=runtime_state.observed_at_utc,
            trust_state=next_state,
            actionable=actionable,
            runtime_state=runtime_state,
            provider_statuses=statuses,
            reasons=reasons,
        )
        return SystemTrustTransition(
            previous_state=previous_state,
            snapshot=snapshot,
            events=self._build_events(snapshot, previous_state),
        )

    def _derive_state(
        self,
        provider_statuses: tuple[ProviderFreshnessStatus, ...],
        runtime_state: RuntimeWindowState,
        previous_state: SystemTrustState | None,
    ) -> tuple[SystemTrustState, bool, tuple[str, ...]]:
        if not runtime_state.scanning_active:
            return SystemTrustState.HEALTHY, False, ("outside_runtime_window",)

        stale_statuses = tuple(status for status in provider_statuses if status.stale)
        if stale_statuses:
            reasons = tuple(
                f"{status.provider}:{status.capability.value}:{status.reason}"
                for status in stale_statuses
            )
            return SystemTrustState.DEGRADED, False, reasons

        if previous_state is SystemTrustState.DEGRADED:
            return (
                SystemTrustState.RECOVERING,
                False,
                ("providers_recovered_waiting_confirmation",),
            )

        return SystemTrustState.HEALTHY, True, ("all_providers_fresh",)

    def _build_events(
        self,
        snapshot: SystemTrustSnapshot,
        previous_state: SystemTrustState | None,
    ) -> tuple[SystemEvent, ...]:
        if not snapshot.runtime_state.scanning_active:
            return ()

        if snapshot.trust_state is SystemTrustState.DEGRADED and previous_state is not SystemTrustState.DEGRADED:
            return (
                SystemEvent(
                    event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                    observed_at=snapshot.observed_at,
                    trust_state=snapshot.trust_state,
                    actionable=snapshot.actionable,
                    reasons=snapshot.reasons,
                ),
            )

        if snapshot.trust_state is SystemTrustState.RECOVERING:
            return (
                SystemEvent(
                    event_type=SystemEventType.PROVIDER_TRUST_RECOVERING,
                    observed_at=snapshot.observed_at,
                    trust_state=snapshot.trust_state,
                    actionable=snapshot.actionable,
                    reasons=snapshot.reasons,
                ),
            )

        if snapshot.trust_state is SystemTrustState.HEALTHY and previous_state is SystemTrustState.RECOVERING:
            return (
                SystemEvent(
                    event_type=SystemEventType.PROVIDER_TRUST_RESTORED,
                    observed_at=snapshot.observed_at,
                    trust_state=snapshot.trust_state,
                    actionable=snapshot.actionable,
                    reasons=snapshot.reasons,
                ),
            )

        return ()
