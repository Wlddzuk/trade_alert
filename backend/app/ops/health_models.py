from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.providers.models import ProviderCapability, ProviderHealthSnapshot
from app.runtime.session_window import RuntimeWindowState


class SystemTrustState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


@dataclass(frozen=True, slots=True)
class ProviderFreshnessRules:
    market_data_max_age_seconds: float = 15.0
    news_max_age_seconds: float = 60.0

    def threshold_for(self, capability: ProviderCapability) -> float:
        if capability is ProviderCapability.MARKET_DATA:
            return self.market_data_max_age_seconds
        return self.news_max_age_seconds


@dataclass(frozen=True, slots=True)
class ProviderFreshnessStatus:
    provider: str
    capability: ProviderCapability
    observed_at: datetime
    threshold_seconds: float
    stale: bool
    within_runtime_window: bool
    reason: str
    snapshot: ProviderHealthSnapshot

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class SystemTrustSnapshot:
    observed_at: datetime
    trust_state: SystemTrustState
    actionable: bool
    runtime_state: RuntimeWindowState
    provider_statuses: tuple[ProviderFreshnessStatus, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
