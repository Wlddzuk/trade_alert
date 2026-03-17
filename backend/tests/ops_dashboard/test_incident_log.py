from __future__ import annotations

from datetime import UTC, datetime

from app.ops.incident_log import IncidentStatus
from app.ops.overview_service import OperationsOverviewService
from app.ops.system_events import SystemEvent, SystemEventType
from app.ops.health_models import SystemTrustState


def test_incident_log_separates_active_issues_from_recent_resolutions() -> None:
    observed_at = datetime(2026, 3, 17, 14, 0, tzinfo=UTC)
    service = OperationsOverviewService()

    incident_log = service.build_incident_log(
        (
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                observed_at=observed_at,
                trust_state=SystemTrustState.DEGRADED,
                actionable=False,
                reasons=("benzinga:news:stale_provider_update",),
            ),
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_RECOVERING,
                observed_at=observed_at.replace(minute=5),
                trust_state=SystemTrustState.RECOVERING,
                actionable=False,
                reasons=("providers_recovered_waiting_confirmation",),
            ),
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_RESTORED,
                observed_at=observed_at.replace(minute=8),
                trust_state=SystemTrustState.HEALTHY,
                actionable=True,
                reasons=("all_providers_fresh",),
            ),
        )
    )

    assert [entry.status for entry in incident_log.active_issues] == [
        IncidentStatus.ACTIVE,
        IncidentStatus.ACTIVE,
    ]
    assert incident_log.active_issues[0].summary == "Provider trust recovering; confirmation still pending."
    assert incident_log.resolved_incidents[0].status is IncidentStatus.RESOLVED
    assert incident_log.resolved_incidents[0].summary == "Provider trust restored."


def test_incident_log_orders_newest_events_first_without_mutating_current_overview() -> None:
    service = OperationsOverviewService()
    older = datetime(2026, 3, 17, 13, 55, tzinfo=UTC)
    newer = datetime(2026, 3, 17, 14, 5, tzinfo=UTC)

    incident_log = service.build_incident_log(
        (
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                observed_at=older,
                trust_state=SystemTrustState.DEGRADED,
                actionable=False,
                reasons=("polygon:market_data:stale_provider_update",),
            ),
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                observed_at=newer,
                trust_state=SystemTrustState.DEGRADED,
                actionable=False,
                reasons=("benzinga:news:stale_provider_update",),
            ),
        )
    )

    assert [entry.observed_at for entry in incident_log.active_issues] == [newer, older]
    assert incident_log.resolved_incidents == ()
