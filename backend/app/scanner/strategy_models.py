from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class InvalidReason(StrEnum):
    MISSING_CATALYST = "missing_catalyst"
    STALE_CATALYST = "stale_catalyst"
    INSUFFICIENT_DAY_MOVE = "insufficient_day_move"
    INSUFFICIENT_DAILY_RVOL = "insufficient_daily_rvol"
    INSUFFICIENT_SHORT_TERM_RVOL = "insufficient_short_term_rvol"
    MISSING_TREND_CONTEXT = "missing_trend_context"
    BELOW_VWAP = "below_vwap"
    EMA_MISALIGNMENT = "ema_misalignment"
    MISSING_PULLBACK_CONTEXT = "missing_pullback_context"
    PULLBACK_TOO_SHALLOW = "pullback_too_shallow"
    PULLBACK_TOO_DEEP = "pullback_too_deep"


@dataclass(frozen=True, slots=True)
class SetupValidity:
    setup_valid: bool
    evaluated_at: datetime
    first_catalyst_at: datetime | None = None
    catalyst_age_seconds: float | None = None
    primary_invalid_reason: InvalidReason | None = None

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        object.__setattr__(self, "evaluated_at", self.evaluated_at.astimezone(UTC))

        if self.first_catalyst_at is not None:
            if self.first_catalyst_at.tzinfo is None or self.first_catalyst_at.utcoffset() is None:
                raise ValueError("first_catalyst_at must be timezone-aware")
            object.__setattr__(self, "first_catalyst_at", self.first_catalyst_at.astimezone(UTC))

        if self.catalyst_age_seconds is not None and self.catalyst_age_seconds < 0:
            raise ValueError("catalyst_age_seconds must be zero or greater")

        if self.setup_valid and self.primary_invalid_reason is not None:
            raise ValueError("valid setups cannot have a primary_invalid_reason")
        if not self.setup_valid and self.primary_invalid_reason is None:
            raise ValueError("invalid setups must have a primary_invalid_reason")
