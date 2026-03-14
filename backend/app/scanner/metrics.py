from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.providers.models import DailyBar, IntradayBar, MarketSnapshot


_ET = ZoneInfo("America/New_York")
_HUNDRED = Decimal("100")


def _decimal_volume(value: int) -> Decimal:
    return Decimal(value)


def _mean(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    return sum(values, start=Decimal("0")) / Decimal(len(values))


def _percentage(numerator: Decimal, denominator: Decimal | None) -> Decimal | None:
    if denominator is None or denominator <= 0:
        return None
    return (numerator / denominator) * _HUNDRED


@dataclass(frozen=True, slots=True)
class MarketMetrics:
    average_daily_volume: Decimal | None
    daily_relative_volume: Decimal | None
    short_term_relative_volume: Decimal | None
    gap_percent: Decimal | None
    change_from_prior_close_percent: Decimal | None
    pullback_from_high_percent: Decimal | None


def average_daily_volume(
    daily_bars: tuple[DailyBar, ...],
    *,
    symbol: str,
    lookback_days: int = 20,
) -> Decimal | None:
    if lookback_days <= 0:
        raise ValueError("lookback_days must be greater than zero")

    matching = tuple(
        _decimal_volume(bar.volume)
        for bar in sorted(
            (bar for bar in daily_bars if bar.symbol == symbol),
            key=lambda bar: bar.trading_date,
        )[-lookback_days:]
    )
    return _mean(matching)


def daily_relative_volume(
    snapshot: MarketSnapshot,
    daily_bars: tuple[DailyBar, ...],
    *,
    lookback_days: int = 20,
) -> tuple[Decimal | None, Decimal | None]:
    adv = average_daily_volume(daily_bars, symbol=snapshot.symbol, lookback_days=lookback_days)
    return adv, _percentage(_decimal_volume(snapshot.session_volume), adv)


def short_term_relative_volume(
    current_bar: IntradayBar | None,
    historical_bars: tuple[IntradayBar, ...],
) -> Decimal | None:
    if current_bar is None:
        return None

    anchor_time = current_bar.start_at.astimezone(_ET).time()
    matching = tuple(
        _decimal_volume(bar.volume)
        for bar in historical_bars
        if bar.symbol == current_bar.symbol and bar.start_at.astimezone(_ET).time() == anchor_time
    )
    baseline = _mean(matching)
    return _percentage(_decimal_volume(current_bar.volume), baseline)


def gap_percent(snapshot: MarketSnapshot) -> Decimal | None:
    if snapshot.open_price is None or snapshot.previous_close is None:
        return None
    return _percentage(snapshot.open_price - snapshot.previous_close, snapshot.previous_close)


def change_from_prior_close_percent(snapshot: MarketSnapshot) -> Decimal | None:
    if snapshot.last_price is None or snapshot.previous_close is None:
        return None
    return _percentage(snapshot.last_price - snapshot.previous_close, snapshot.previous_close)


def pullback_from_high_percent(snapshot: MarketSnapshot) -> Decimal | None:
    if snapshot.high_price is None or snapshot.last_price is None:
        return None
    if snapshot.high_price <= 0:
        return None
    drawdown = max(snapshot.high_price - snapshot.last_price, Decimal("0"))
    return _percentage(drawdown, snapshot.high_price)


def build_market_metrics(
    snapshot: MarketSnapshot,
    *,
    daily_bars: tuple[DailyBar, ...],
    current_bar: IntradayBar | None = None,
    historical_intraday_bars: tuple[IntradayBar, ...] = (),
    lookback_days: int = 20,
) -> MarketMetrics:
    adv, daily_rvol = daily_relative_volume(snapshot, daily_bars, lookback_days=lookback_days)
    return MarketMetrics(
        average_daily_volume=adv,
        daily_relative_volume=daily_rvol,
        short_term_relative_volume=short_term_relative_volume(current_bar, historical_intraday_bars),
        gap_percent=gap_percent(snapshot),
        change_from_prior_close_percent=change_from_prior_close_percent(snapshot),
        pullback_from_high_percent=pullback_from_high_percent(snapshot),
    )
