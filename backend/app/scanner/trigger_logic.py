from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .trigger_policy import TriggerBarSelection


@dataclass(frozen=True, slots=True)
class TriggerEvaluation:
    triggered: bool
    interval_seconds: int
    used_fallback: bool
    trigger_price: Decimal | None = None
    trigger_bar_started_at: datetime | None = None
    bullish_confirmation: bool | None = None

    def __post_init__(self) -> None:
        if self.trigger_bar_started_at is not None:
            if self.trigger_bar_started_at.tzinfo is None or self.trigger_bar_started_at.utcoffset() is None:
                raise ValueError("trigger_bar_started_at must be timezone-aware")
            object.__setattr__(self, "trigger_bar_started_at", self.trigger_bar_started_at.astimezone(UTC))
        if self.triggered and self.trigger_price is None:
            raise ValueError("triggered evaluations must include a trigger_price")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    return value.astimezone(UTC)


def evaluate_first_break_trigger(
    selection: TriggerBarSelection,
    *,
    as_of: datetime | None = None,
    max_trigger_age_seconds: int | None = None,
) -> TriggerEvaluation:
    as_of_utc = _ensure_utc(as_of) if as_of is not None else None
    fresh_after = (
        as_of_utc - timedelta(seconds=max_trigger_age_seconds)
        if as_of_utc is not None and max_trigger_age_seconds is not None
        else None
    )

    if len(selection.bars) < 2:
        return TriggerEvaluation(
            triggered=False,
            interval_seconds=selection.interval_seconds,
            used_fallback=selection.used_fallback,
        )

    for previous_bar, current_bar in zip(selection.bars, selection.bars[1:]):
        if as_of_utc is not None and current_bar.start_at > as_of_utc:
            continue
        if fresh_after is not None and previous_bar.start_at < fresh_after:
            continue
        if fresh_after is not None and current_bar.start_at < fresh_after:
            continue
        if previous_bar.high_price is None or current_bar.high_price is None:
            continue
        if previous_bar.high_price <= 0 or current_bar.high_price <= 0:
            continue
        if current_bar.high_price <= previous_bar.high_price:
            continue

        bullish_confirmation = None
        if current_bar.open_price is not None and current_bar.close_price is not None:
            bullish_confirmation = current_bar.close_price > current_bar.open_price
        return TriggerEvaluation(
            triggered=True,
            interval_seconds=selection.interval_seconds,
            used_fallback=selection.used_fallback,
            trigger_price=previous_bar.high_price,
            trigger_bar_started_at=current_bar.start_at,
            bullish_confirmation=bullish_confirmation,
        )

    return TriggerEvaluation(
        triggered=False,
        interval_seconds=selection.interval_seconds,
        used_fallback=selection.used_fallback,
    )
