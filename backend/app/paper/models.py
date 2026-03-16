from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.alerts.models import OpenTradeSnapshot
from app.providers.models import ensure_utc, normalize_symbol


def _coerce_decimal(
    value: Decimal | float | int | str,
    *,
    field_name: str,
) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return decimal_value


def _coerce_ratio(value: Decimal | float | int | str) -> Decimal:
    ratio = Decimal(str(value))
    if ratio <= 0 or ratio > 1:
        raise ValueError("partial_fill_ratio must be greater than zero and at most one")
    return ratio


class PaperTradeStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PaperExitReason(StrEnum):
    STOP_HIT = "stop_hit"
    TARGET_HIT = "target_hit"
    WEAK_FOLLOW_THROUGH = "weak_follow_through"
    MOMENTUM_FAILURE = "momentum_failure"
    MANUAL_CLOSE = "manual_close"


@dataclass(frozen=True, slots=True)
class PaperFillPolicy:
    slippage_bps_per_side: Decimal | float | int | str = "5"
    partial_fills_enabled: bool = False

    def __post_init__(self) -> None:
        slippage = _coerce_decimal(self.slippage_bps_per_side, field_name="slippage_bps_per_side")
        object.__setattr__(self, "slippage_bps_per_side", slippage)

    def apply_entry_slippage(self, requested_price: Decimal) -> Decimal:
        return requested_price * (Decimal("1") + (self.slippage_bps_per_side / Decimal("10000")))


@dataclass(frozen=True, slots=True)
class PaperTrade:
    trade_id: str
    symbol: str
    opened_at: datetime
    requested_entry_price: Decimal | float | int | str
    fill_price: Decimal | float | int | str
    stop_price: Decimal | float | int | str
    target_price: Decimal | float | int | str
    requested_quantity: int
    filled_quantity: int
    partial_fill_ratio: Decimal | float | int | str = "1"
    status: PaperTradeStatus = PaperTradeStatus.OPEN
    closed_at: datetime | None = None
    close_price: Decimal | float | int | str | None = None
    exit_reason: PaperExitReason | None = None

    def __post_init__(self) -> None:
        cleaned_trade_id = self.trade_id.strip()
        if not cleaned_trade_id:
            raise ValueError("trade_id must not be empty")
        object.__setattr__(self, "trade_id", cleaned_trade_id)
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "opened_at", ensure_utc(self.opened_at, field_name="opened_at"))
        object.__setattr__(
            self,
            "requested_entry_price",
            _coerce_decimal(self.requested_entry_price, field_name="requested_entry_price"),
        )
        object.__setattr__(self, "fill_price", _coerce_decimal(self.fill_price, field_name="fill_price"))
        object.__setattr__(self, "stop_price", _coerce_decimal(self.stop_price, field_name="stop_price"))
        object.__setattr__(self, "target_price", _coerce_decimal(self.target_price, field_name="target_price"))
        object.__setattr__(self, "partial_fill_ratio", _coerce_ratio(self.partial_fill_ratio))
        if self.requested_quantity <= 0:
            raise ValueError("requested_quantity must be greater than zero")
        if self.filled_quantity <= 0:
            raise ValueError("filled_quantity must be greater than zero")
        if self.filled_quantity > self.requested_quantity:
            raise ValueError("filled_quantity cannot exceed requested_quantity")
        if self.stop_price >= self.requested_entry_price:
            raise ValueError("stop_price must stay below requested_entry_price")
        if self.target_price <= self.requested_entry_price:
            raise ValueError("target_price must stay above requested_entry_price")

        if self.closed_at is not None:
            object.__setattr__(self, "closed_at", ensure_utc(self.closed_at, field_name="closed_at"))
        if self.close_price is not None:
            object.__setattr__(self, "close_price", _coerce_decimal(self.close_price, field_name="close_price"))

        if self.status is PaperTradeStatus.OPEN:
            if self.closed_at is not None or self.close_price is not None or self.exit_reason is not None:
                raise ValueError("open trades cannot include close fields")
        elif self.status is PaperTradeStatus.CLOSED:
            if self.closed_at is None or self.close_price is None or self.exit_reason is None:
                raise ValueError("closed trades require closed_at, close_price, and exit_reason")

    @property
    def open_snapshot(self) -> OpenTradeSnapshot:
        return OpenTradeSnapshot(
            trade_id=self.trade_id,
            symbol=self.symbol,
            opened_at=self.opened_at,
            entry_price=self.fill_price,
            stop_price=self.stop_price,
            target_price=self.target_price,
            quantity=self.filled_quantity,
        )

    @property
    def risk_per_share(self) -> Decimal:
        return self.fill_price - self.stop_price

    @property
    def realized_pnl(self) -> Decimal | None:
        if self.close_price is None:
            return None
        return (self.close_price - self.fill_price) * Decimal(self.filled_quantity)

    def with_levels(
        self,
        *,
        stop_price: Decimal | float | int | str | None = None,
        target_price: Decimal | float | int | str | None = None,
    ) -> "PaperTrade":
        if self.status is not PaperTradeStatus.OPEN:
            raise ValueError("level adjustments require an open trade")
        return replace(
            self,
            stop_price=self.stop_price if stop_price is None else _coerce_decimal(stop_price, field_name="stop_price"),
            target_price=self.target_price
            if target_price is None
            else _coerce_decimal(target_price, field_name="target_price"),
        )

    def close(
        self,
        *,
        closed_at: datetime,
        close_price: Decimal | float | int | str,
        exit_reason: PaperExitReason,
    ) -> "PaperTrade":
        if self.status is not PaperTradeStatus.OPEN:
            raise ValueError("trade is already closed")
        return replace(
            self,
            status=PaperTradeStatus.CLOSED,
            closed_at=ensure_utc(closed_at, field_name="closed_at"),
            close_price=_coerce_decimal(close_price, field_name="close_price"),
            exit_reason=exit_reason,
        )
