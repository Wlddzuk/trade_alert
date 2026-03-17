from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .system_events import SystemEvent, SystemEventType


class IncidentStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


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
