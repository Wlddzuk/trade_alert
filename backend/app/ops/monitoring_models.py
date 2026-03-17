from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.ops.health_models import ProviderFreshnessStatus
from app.runtime.session_window import SessionPhase


class OperationsStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    OFFLINE = "offline_session_closed"


class ScannerLoopState(StrEnum):
    RUNNING = "running"
    STALE = "stale"
    IDLE = "idle"


class AlertDeliveryState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline_session_closed"


@dataclass(frozen=True, slots=True)
class ProviderFreshnessView:
    provider: str
    capability: str
    status: str
    freshness_age_seconds: float | None
    threshold_seconds: float
    reason: str
    last_update_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScannerLoopSnapshot:
    observed_at: datetime
    last_success_at: datetime | None
    max_idle_seconds: float = 90.0
    last_error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        if self.last_success_at is not None:
            object.__setattr__(self, "last_success_at", _ensure_utc(self.last_success_at, "last_success_at"))
        if self.max_idle_seconds <= 0:
            raise ValueError("max_idle_seconds must be greater than zero")


@dataclass(frozen=True, slots=True)
class ScannerLoopHealth:
    state: ScannerLoopState
    summary: str
    last_success_at: datetime | None
    idle_seconds: float | None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class AlertDeliverySnapshot:
    observed_at: datetime
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int = 0
    last_failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        if self.last_attempt_at is not None:
            object.__setattr__(self, "last_attempt_at", _ensure_utc(self.last_attempt_at, "last_attempt_at"))
        if self.last_success_at is not None:
            object.__setattr__(self, "last_success_at", _ensure_utc(self.last_success_at, "last_success_at"))
        if self.consecutive_failures < 0:
            raise ValueError("consecutive_failures must be zero or greater")


@dataclass(frozen=True, slots=True)
class AlertDeliveryHealth:
    state: AlertDeliveryState
    summary: str
    consecutive_failures: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class OperationsOverview:
    observed_at: datetime
    status: OperationsStatus
    headline: str
    actionable: bool
    runtime_phase: SessionPhase
    provider_freshness: tuple[ProviderFreshnessView, ...]
    scanner_loop: ScannerLoopHealth
    alert_delivery: AlertDeliveryHealth
    trust_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "provider_freshness", tuple(self.provider_freshness))
        object.__setattr__(self, "trust_reasons", tuple(self.trust_reasons))


def build_provider_freshness_views(
    statuses: tuple[ProviderFreshnessStatus, ...],
) -> tuple[ProviderFreshnessView, ...]:
    return tuple(
        ProviderFreshnessView(
            provider=status.provider,
            capability=status.capability.value,
            status="stale" if status.stale else "fresh",
            freshness_age_seconds=status.snapshot.freshness_age_seconds,
            threshold_seconds=status.threshold_seconds,
            reason=status.reason,
            last_update_at=status.snapshot.last_update_at,
        )
        for status in statuses
    )


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
