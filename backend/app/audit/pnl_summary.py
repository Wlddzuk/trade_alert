from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from .review_models import TradeReviewFeed
from .review_service import TradeReviewService
from .models import LifecycleEvent


@dataclass(frozen=True, slots=True)
class DailyPnl:
    trading_day: date
    realized_pnl: Decimal
    trade_count: int
    win_rate: Decimal


@dataclass(frozen=True, slots=True)
class PnlSummary:
    today: DailyPnl
    cumulative_realized_pnl: Decimal
    cumulative_trade_count: int
    cumulative_win_rate: Decimal
    history: tuple[DailyPnl, ...]


class PnlSummaryService:
    def __init__(self, review_service: TradeReviewService | None = None) -> None:
        self._review_service = review_service or TradeReviewService()

    def build(self, events: tuple[LifecycleEvent, ...], *, today: date | datetime) -> PnlSummary:
        trade_feed = self._review_service.build_completed_trade_feed(events)
        as_of_day = today.astimezone(UTC).date() if isinstance(today, datetime) else today

        history = tuple(
            DailyPnl(
                trading_day=day.trading_day,
                realized_pnl=day.realized_pnl,
                trade_count=day.trade_count,
                win_rate=_win_rate(day.win_count, day.trade_count),
            )
            for day in trade_feed.days
        )
        today_row = next(
            (row for row in history if row.trading_day == as_of_day),
            DailyPnl(
                trading_day=as_of_day,
                realized_pnl=Decimal("0"),
                trade_count=0,
                win_rate=Decimal("0"),
            ),
        )
        cumulative_trade_count = sum(row.trade_count for row in history)
        cumulative_wins = sum(
            1
            for day in trade_feed.days
            for trade in day.trades
            if trade.realized_pnl > 0
        )
        return PnlSummary(
            today=today_row,
            cumulative_realized_pnl=sum((row.realized_pnl for row in history), start=Decimal("0")),
            cumulative_trade_count=cumulative_trade_count,
            cumulative_win_rate=_win_rate(cumulative_wins, cumulative_trade_count),
            history=history,
        )


def _win_rate(wins: int, trade_count: int) -> Decimal:
    if trade_count == 0:
        return Decimal("0")
    return (Decimal(wins) / Decimal(trade_count)).quantize(Decimal("0.01"))
