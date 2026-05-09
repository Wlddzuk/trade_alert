from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Iterable

from app.providers.models import IntradayBar, MarketSnapshot


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(UTC)


def _ema(values: tuple[Decimal, ...], *, period: int) -> Decimal | None:
    if period <= 0:
        raise ValueError("period must be greater than zero")
    if len(values) < period:
        return None

    multiplier = Decimal("2") / Decimal(period + 1)
    seed = sum(values[:period], start=Decimal("0")) / Decimal(period)
    current = seed
    for value in values[period:]:
        current = ((value - current) * multiplier) + current
    return current


def _ema_series(values: tuple[Decimal, ...], *, period: int) -> tuple[Decimal | None, ...]:
    if period <= 0:
        raise ValueError("period must be greater than zero")
    if len(values) < period:
        return tuple(None for _ in values)

    multiplier = Decimal("2") / Decimal(period + 1)
    seed = sum(values[:period], start=Decimal("0")) / Decimal(period)
    series: list[Decimal | None] = [None] * (period - 1)
    series.append(seed)
    current = seed
    for value in values[period:]:
        current = ((value - current) * multiplier) + current
        series.append(current)
    return tuple(series)


def find_ema_tagged_pullback_candle(
    bars: tuple[IntradayBar, ...],
    *,
    ema_period: int = 9,
) -> IntradayBar | None:
    """Most recent bar whose [low, high] straddles the EMA at that bar's close.

    Implements the Ross Cameron pullback rule: the structural stop sits below
    the low of the candle that *tags* the EMA. If no candle tags the EMA, there
    is no valid pullback, and the caller must treat the setup as invalid.
    """
    bars_with_close = tuple(bar for bar in bars if bar.close_price is not None)
    if len(bars_with_close) < ema_period:
        return None
    closes = tuple(bar.close_price for bar in bars_with_close)
    ema_values = _ema_series(closes, period=ema_period)

    most_recent_tag: IntradayBar | None = None
    for bar, ema in zip(bars_with_close, ema_values):
        if ema is None or bar.low_price is None or bar.high_price is None:
            continue
        if bar.low_price <= ema <= bar.high_price:
            most_recent_tag = bar
    return most_recent_tag


def pullback_retracement_percent(
    *,
    impulse_low: Decimal | None,
    impulse_high: Decimal | None,
    pullback_low: Decimal | None,
) -> Decimal | None:
    if impulse_low is None or impulse_high is None or pullback_low is None:
        return None
    if impulse_high <= impulse_low:
        return None

    impulse_leg = impulse_high - impulse_low
    retracement = max(impulse_high - pullback_low, Decimal("0"))
    return (retracement / impulse_leg) * Decimal("100")


@dataclass(frozen=True, slots=True)
class ContextFeatures:
    observed_at: datetime
    vwap: Decimal | None
    ema_9: Decimal | None
    ema_20: Decimal | None
    ema_200: Decimal | None = None
    impulse_low: Decimal | None = None
    pullback_low: Decimal | None = None
    pullback_retracement_percent: Decimal | None = None
    pullback_volume_lighter: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _ensure_aware(self.observed_at))


def build_context_features(
    snapshot: MarketSnapshot,
    intraday_bars: Iterable[IntradayBar],
    *,
    impulse_low: Decimal | None = None,
    pullback_low: Decimal | None = None,
    pullback_volume_lighter: bool | None = None,
    include_ema_200: bool = False,
) -> ContextFeatures:
    matching_bars = tuple(
        sorted(
            (bar for bar in intraday_bars if bar.symbol == snapshot.symbol),
            key=lambda bar: bar.start_at,
        )
    )
    close_series = tuple(bar.close_price for bar in matching_bars if bar.close_price is not None)
    derived_pullback_low = pullback_low
    if derived_pullback_low is None:
        tagged_bar = find_ema_tagged_pullback_candle(matching_bars, ema_period=9)
        if tagged_bar is not None and tagged_bar.low_price is not None:
            derived_pullback_low = tagged_bar.low_price

    derived_impulse_low = impulse_low or snapshot.low_price
    return ContextFeatures(
        observed_at=snapshot.observed_at,
        vwap=snapshot.vwap,
        ema_9=_ema(close_series, period=9),
        ema_20=_ema(close_series, period=20),
        ema_200=_ema(close_series, period=200) if include_ema_200 else None,
        impulse_low=derived_impulse_low,
        pullback_low=derived_pullback_low,
        pullback_retracement_percent=pullback_retracement_percent(
            impulse_low=derived_impulse_low,
            impulse_high=snapshot.high_price,
            pullback_low=derived_pullback_low,
        ),
        pullback_volume_lighter=pullback_volume_lighter,
    )
