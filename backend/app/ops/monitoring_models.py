from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .health_models import SystemTrustState


class MonitoringStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    OFFLINE = "offline"


class HealthSeverity(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class ProviderFreshnessOverview:
    provider: str
    capability: str
    freshness_age_seconds: float | None
    threshold_seconds: float
    stale: bool
    status: HealthSeverity
    reason: str


@dataclass(frozen=True, slots=True)
class ScannerLoopHealth:
    observed_at: datetime
    last_iteration_at: datetime | None
    lag_seconds: float | None
    status: HealthSeverity
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        if self.last_iteration_at is not None:
            object.__setattr__(
                self,
                "last_iteration_at",
                _ensure_utc(self.last_iteration_at, "last_iteration_at"),
            )


@dataclass(frozen=True, slots=True)
class AlertDeliveryStatus:
    observed_at: datetime
    status: HealthSeverity
    summary: str
    consecutive_failures: int = 0
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        if self.last_attempt_at is not None:
            object.__setattr__(
                self,
                "last_attempt_at",
                _ensure_utc(self.last_attempt_at, "last_attempt_at"),
            )
        if self.last_success_at is not None:
            object.__setattr__(
                self,
                "last_success_at",
                _ensure_utc(self.last_success_at, "last_success_at"),
            )


@dataclass(frozen=True, slots=True)
class StatusOverview:
    observed_at: datetime
    status: MonitoringStatus
    actionable: bool
    headline: str
    session_label: str
    trust_state: SystemTrustState
    trust_reasons: tuple[str, ...]
    stale_context_visible: bool
    provider_freshness: tuple[ProviderFreshnessOverview, ...]
    scanner_loop: ScannerLoopHealth
    alert_delivery: AlertDeliveryStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "trust_reasons", tuple(self.trust_reasons))
        object.__setattr__(self, "provider_freshness", tuple(self.provider_freshness))


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
