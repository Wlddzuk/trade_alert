from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .health_models import SystemTrustState


class SystemEventType(StrEnum):
    PROVIDER_TRUST_DEGRADED = "provider_trust_degraded"
    PROVIDER_TRUST_RECOVERING = "provider_trust_recovering"
    PROVIDER_TRUST_RESTORED = "provider_trust_restored"


@dataclass(frozen=True, slots=True)
class SystemEvent:
    event_type: SystemEventType
    observed_at: datetime
    trust_state: SystemTrustState
    actionable: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        object.__setattr__(self, "reasons", tuple(self.reasons))
