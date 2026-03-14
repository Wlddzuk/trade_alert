from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo


class SessionPhase(StrEnum):
    OFFLINE = "offline"
    PREMARKET = "premarket"
    REGULAR = "regular"
    POST_CLOSE = "post_close"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class RuntimeWindowState:
    observed_at_utc: datetime
    observed_at_et: datetime
    phase: SessionPhase
    scanning_active: bool


@dataclass(frozen=True, slots=True)
class RuntimeWindow:
    timezone_name: str = "America/New_York"
    premarket_start: time = time(4, 0)
    regular_open: time = time(9, 30)
    regular_close: time = time(16, 0)
    stop_time: time = time(16, 30)

    def __post_init__(self) -> None:
        if not (self.premarket_start < self.regular_open < self.regular_close < self.stop_time):
            raise ValueError("runtime window times must be strictly increasing")

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def phase_at(self, observed_at: datetime) -> SessionPhase:
        local_time = self._local_datetime(observed_at).timetz().replace(tzinfo=None)
        if local_time < self.premarket_start:
            return SessionPhase.OFFLINE
        if local_time < self.regular_open:
            return SessionPhase.PREMARKET
        if local_time < self.regular_close:
            return SessionPhase.REGULAR
        if local_time < self.stop_time:
            return SessionPhase.POST_CLOSE
        return SessionPhase.OFFLINE

    def is_scanning_active(self, observed_at: datetime) -> bool:
        return self.phase_at(observed_at) is not SessionPhase.OFFLINE

    def status_at(self, observed_at: datetime) -> RuntimeWindowState:
        observed_at_utc = _ensure_aware(observed_at)
        observed_at_et = observed_at_utc.astimezone(self.timezone)
        phase = self.phase_at(observed_at_utc)
        return RuntimeWindowState(
            observed_at_utc=observed_at_utc,
            observed_at_et=observed_at_et,
            phase=phase,
            scanning_active=phase is not SessionPhase.OFFLINE,
        )

    def _local_datetime(self, observed_at: datetime) -> datetime:
        return _ensure_aware(observed_at).astimezone(self.timezone)
