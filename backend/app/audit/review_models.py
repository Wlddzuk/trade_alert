from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from .models import LifecycleEvent


@dataclass(frozen=True, slots=True)
class CompletedTradeReview:
    trade_id: str
    symbol: str
    trading_day: date
    closed_at: datetime
    opened_at: datetime
    entry_decision: str | None
    operator_commands: tuple[str, ...]
    entry_price: Decimal
    close_price: Decimal
    quantity: int
    exit_reason: str | None
    realized_pnl: Decimal
    raw_events: tuple[LifecycleEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "closed_at", _ensure_utc(self.closed_at, "closed_at"))
        object.__setattr__(self, "opened_at", _ensure_utc(self.opened_at, "opened_at"))
        object.__setattr__(self, "raw_events", tuple(self.raw_events))
        object.__setattr__(self, "operator_commands", tuple(self.operator_commands))


@dataclass(frozen=True, slots=True)
class TradeReviewDay:
    trading_day: date
    trades: tuple[CompletedTradeReview, ...]
    realized_pnl: Decimal
    trade_count: int
    win_count: int


@dataclass(frozen=True, slots=True)
class TradeReviewFeed:
    days: tuple[TradeReviewDay, ...]
    total_trades: int


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
