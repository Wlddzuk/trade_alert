from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def _as_decimal(value: Decimal | float | int | str, *, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return decimal_value


@dataclass(frozen=True, slots=True)
class StrategyDefaults:
    max_catalyst_age_minutes: int = 90
    min_move_on_day_percent: Decimal | float | int | str = Decimal("5")
    min_daily_relative_volume: Decimal | float | int | str = Decimal("1.0")
    min_short_term_relative_volume: Decimal | float | int | str = Decimal("1.0")
    min_pullback_retracement_percent: Decimal | float | int | str = Decimal("35")
    max_pullback_retracement_percent: Decimal | float | int | str = Decimal("60")
    preferred_trigger_interval_seconds: int = 15
    fallback_trigger_interval_seconds: int = 60

    def __post_init__(self) -> None:
        if self.max_catalyst_age_minutes <= 0:
            raise ValueError("max_catalyst_age_minutes must be greater than zero")
        if self.preferred_trigger_interval_seconds <= 0:
            raise ValueError("preferred_trigger_interval_seconds must be greater than zero")
        if self.fallback_trigger_interval_seconds <= 0:
            raise ValueError("fallback_trigger_interval_seconds must be greater than zero")
        if self.preferred_trigger_interval_seconds >= self.fallback_trigger_interval_seconds:
            raise ValueError("preferred trigger interval must be lower than the fallback interval")

        min_move = _as_decimal(self.min_move_on_day_percent, field_name="min_move_on_day_percent")
        min_daily_rvol = _as_decimal(self.min_daily_relative_volume, field_name="min_daily_relative_volume")
        min_short_term_rvol = _as_decimal(
            self.min_short_term_relative_volume,
            field_name="min_short_term_relative_volume",
        )
        min_pullback = _as_decimal(
            self.min_pullback_retracement_percent,
            field_name="min_pullback_retracement_percent",
        )
        max_pullback = _as_decimal(
            self.max_pullback_retracement_percent,
            field_name="max_pullback_retracement_percent",
        )
        if min_pullback >= max_pullback:
            raise ValueError("min pullback retracement must be lower than max pullback retracement")

        object.__setattr__(self, "min_move_on_day_percent", min_move)
        object.__setattr__(self, "min_daily_relative_volume", min_daily_rvol)
        object.__setattr__(self, "min_short_term_relative_volume", min_short_term_rvol)
        object.__setattr__(self, "min_pullback_retracement_percent", min_pullback)
        object.__setattr__(self, "max_pullback_retracement_percent", max_pullback)
