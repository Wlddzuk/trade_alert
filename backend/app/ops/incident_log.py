from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .alert_delivery_health import AlertDeliveryHealthReport
from .system_events import SystemEvent, SystemEventType


class IncidentStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


IncidentState = IncidentStatus


@dataclass(frozen=True, slots=True)
class IncidentEntry:
    observed_at: datetime
    event_type: str
    status: IncidentStatus
    summary: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True, slots=True)
class IncidentLogView:
    active_issues: tuple[IncidentEntry, ...]
    resolved_incidents: tuple[IncidentEntry, ...]


IncidentLog = IncidentLogView


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    incident_id: str
    occurred_at: datetime
    title: str
    summary: str
    severity: str
    state: IncidentStatus
    source: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class IncidentLogReport:
    recent_critical_issues: tuple[IncidentRecord, ...]
    recently_resolved: tuple[IncidentRecord, ...]


def build_incident_log(events: tuple[SystemEvent, ...], *, limit: int = 10) -> IncidentLogView:
    ordered = sorted(events, key=lambda event: event.observed_at, reverse=True)
    active: list[IncidentEntry] = []
    resolved: list[IncidentEntry] = []
    for event in ordered:
        entry = IncidentEntry(
            observed_at=event.observed_at,
            event_type=event.event_type.value,
            status=_status_for_event(event.event_type),
            summary=_summary_for_event(event.event_type),
            reasons=event.reasons,
        )
        if entry.status is IncidentStatus.ACTIVE:
            active.append(entry)
        else:
            resolved.append(entry)
    return IncidentLogView(
        active_issues=tuple(active[:limit]),
        resolved_incidents=tuple(resolved[:limit]),
    )


def _status_for_event(event_type: SystemEventType) -> IncidentStatus:
    if event_type is SystemEventType.PROVIDER_TRUST_RESTORED:
        return IncidentStatus.RESOLVED
    return IncidentStatus.ACTIVE


def _summary_for_event(event_type: SystemEventType) -> str:
    if event_type is SystemEventType.PROVIDER_TRUST_DEGRADED:
        return "Provider trust degraded."
    if event_type is SystemEventType.PROVIDER_TRUST_RECOVERING:
        return "Provider trust recovering; confirmation still pending."
    return "Provider trust restored."


class IncidentLogService:
    def build(
        self,
        events: tuple[SystemEvent, ...],
        *,
        delivery_report: AlertDeliveryHealthReport | None = None,
        limit: int = 5,
    ) -> IncidentLogReport:
        critical = list(self._critical_incidents(events))
        resolved = list(self._resolved_incidents(events))
        if delivery_report is not None:
            for failure in delivery_report.recent_failures:
                critical.append(
                    IncidentRecord(
                        incident_id=f"alert-delivery:{int(failure.observed_at.timestamp())}",
                        occurred_at=failure.observed_at,
                        title="Alert delivery failure",
                        summary=failure.reason,
                        severity="critical",
                        state=IncidentStatus.ACTIVE,
                        source="alert_delivery",
                    )
                )

        return IncidentLogReport(
            recent_critical_issues=tuple(
                sorted(critical, key=lambda incident: incident.occurred_at, reverse=True)[:limit]
            ),
            recently_resolved=tuple(
                sorted(resolved, key=lambda incident: incident.occurred_at, reverse=True)[:limit]
            ),
        )

    def _critical_incidents(self, events: tuple[SystemEvent, ...]) -> tuple[IncidentRecord, ...]:
        return tuple(
            IncidentRecord(
                incident_id=f"{event.event_type.value}:{int(event.observed_at.timestamp())}",
                occurred_at=event.observed_at,
                title="Provider trust degraded",
                summary=", ".join(event.reasons) if event.reasons else "Provider trust degraded.",
                severity="critical",
                state=IncidentStatus.ACTIVE,
                source="system_trust",
            )
            for event in events
            if event.event_type is SystemEventType.PROVIDER_TRUST_DEGRADED
        )

    def _resolved_incidents(self, events: tuple[SystemEvent, ...]) -> tuple[IncidentRecord, ...]:
        records: list[IncidentRecord] = []
        for event in events:
            if event.event_type is SystemEventType.PROVIDER_TRUST_RECOVERING:
                records.append(
                    IncidentRecord(
                        incident_id=f"{event.event_type.value}:{int(event.observed_at.timestamp())}",
                        occurred_at=event.observed_at,
                        title="Provider trust recovering",
                        summary=", ".join(event.reasons) if event.reasons else "Providers are stabilizing.",
                        severity="info",
                        state=IncidentStatus.RESOLVED,
                        source="system_trust",
                    )
                )
            elif event.event_type is SystemEventType.PROVIDER_TRUST_RESTORED:
                records.append(
                    IncidentRecord(
                        incident_id=f"{event.event_type.value}:{int(event.observed_at.timestamp())}",
                        occurred_at=event.observed_at,
                        title="Provider trust restored",
                        summary=", ".join(event.reasons) if event.reasons else "Providers are healthy again.",
                        severity="info",
                        state=IncidentStatus.RESOLVED,
                        source="system_trust",
                    )
                )
        return tuple(records)
