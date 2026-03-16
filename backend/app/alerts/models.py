from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.providers.models import ensure_utc, normalize_symbol
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag


def _coerce_decimal(
    value: Decimal | float | int | str,
    *,
    field_name: str,
    allow_negative: bool = False,
) -> Decimal:
    decimal_value = Decimal(str(value))
    if not allow_negative and decimal_value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return decimal_value


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _format_alert_id(symbol: str, state: str, surfaced_at: datetime) -> str:
    return f"{symbol.lower()}-{state}-{int(surfaced_at.timestamp())}"


class PreEntryAlertState(StrEnum):
    WATCH = "watch"
    ACTIONABLE = "actionable"
    BLOCKED = "blocked"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TradeProposal:
    symbol: str
    entry_price: Decimal | float | int | str
    stop_price: Decimal | float | int | str
    target_price: Decimal | float | int | str
    thesis: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "entry_price", _coerce_decimal(self.entry_price, field_name="entry_price"))
        object.__setattr__(self, "stop_price", _coerce_decimal(self.stop_price, field_name="stop_price"))
        object.__setattr__(self, "target_price", _coerce_decimal(self.target_price, field_name="target_price"))
        object.__setattr__(self, "thesis", _clean_optional_text(self.thesis))

        if self.stop_price >= self.entry_price:
            raise ValueError("stop_price must stay below entry_price for long setups")
        if self.target_price <= self.entry_price:
            raise ValueError("target_price must stay above entry_price for long setups")


@dataclass(frozen=True, slots=True)
class PreEntryAlert:
    state: PreEntryAlertState
    projection: StrategyProjection
    proposal: TradeProposal
    rank: int
    surfaced_at: datetime
    status_reason: str | None = None
    alert_id: str | None = None

    def __post_init__(self) -> None:
        surfaced_at = ensure_utc(self.surfaced_at, field_name="surfaced_at")
        object.__setattr__(self, "surfaced_at", surfaced_at)
        object.__setattr__(self, "status_reason", _clean_optional_text(self.status_reason))
        if self.rank <= 0:
            raise ValueError("rank must be greater than zero")
        if self.projection.row.symbol != self.proposal.symbol:
            raise ValueError("projection and proposal must reference the same symbol")
        if self.state is PreEntryAlertState.WATCH and self.projection.stage_tag is not StrategyStageTag.BUILDING:
            raise ValueError("watch alerts require a building projection")
        if self.state in {PreEntryAlertState.ACTIONABLE, PreEntryAlertState.BLOCKED} and (
            self.projection.stage_tag is not StrategyStageTag.TRIGGER_READY
        ):
            raise ValueError("actionable and blocked alerts require a trigger-ready projection")
        if self.state is PreEntryAlertState.BLOCKED and self.status_reason is None:
            raise ValueError("blocked alerts require a status_reason")
        if (
            self.state is PreEntryAlertState.REJECTED
            and self.status_reason is None
            and self.projection.primary_invalid_reason is None
        ):
            raise ValueError("rejected alerts require a status_reason or primary_invalid_reason")

        alert_id = _clean_optional_text(self.alert_id)
        if alert_id is None:
            alert_id = _format_alert_id(self.symbol, self.state.value, self.surfaced_at)
        object.__setattr__(self, "alert_id", alert_id)

    @property
    def symbol(self) -> str:
        return self.projection.row.symbol

    @property
    def approval_capable(self) -> bool:
        return self.state is PreEntryAlertState.ACTIONABLE

    @property
    def display_reason(self) -> str | None:
        return self.status_reason or self.projection.primary_invalid_reason


def project_pre_entry_alert(
    projection: StrategyProjection,
    proposal: TradeProposal,
    *,
    state: PreEntryAlertState,
    rank: int,
    surfaced_at: datetime | None = None,
    status_reason: str | None = None,
) -> PreEntryAlert:
    return PreEntryAlert(
        state=state,
        projection=projection,
        proposal=proposal,
        rank=rank,
        surfaced_at=surfaced_at or projection.row.observed_at,
        status_reason=status_reason,
    )


@dataclass(frozen=True, slots=True)
class OpenTradeSnapshot:
    trade_id: str
    symbol: str
    opened_at: datetime
    entry_price: Decimal | float | int | str
    stop_price: Decimal | float | int | str
    target_price: Decimal | float | int | str
    quantity: int | None = None

    def __post_init__(self) -> None:
        cleaned_trade_id = self.trade_id.strip()
        if not cleaned_trade_id:
            raise ValueError("trade_id must not be empty")
        object.__setattr__(self, "trade_id", cleaned_trade_id)
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "opened_at", ensure_utc(self.opened_at, field_name="opened_at"))
        object.__setattr__(self, "entry_price", _coerce_decimal(self.entry_price, field_name="entry_price"))
        object.__setattr__(self, "stop_price", _coerce_decimal(self.stop_price, field_name="stop_price"))
        object.__setattr__(self, "target_price", _coerce_decimal(self.target_price, field_name="target_price"))
        if self.stop_price >= self.entry_price:
            raise ValueError("stop_price must stay below entry_price for long trades")
        if self.target_price <= self.entry_price:
            raise ValueError("target_price must stay above entry_price for long trades")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")


@dataclass(frozen=True, slots=True)
class TradeOpenedEvent:
    trade: OpenTradeSnapshot
    observed_at: datetime
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        object.__setattr__(self, "note", _clean_optional_text(self.note))


@dataclass(frozen=True, slots=True)
class TradeAdjustedEvent:
    trade: OpenTradeSnapshot
    observed_at: datetime
    new_stop_price: Decimal | float | int | str | None = None
    new_target_price: Decimal | float | int | str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        object.__setattr__(self, "note", _clean_optional_text(self.note))

        stop_price = self.trade.stop_price
        if self.new_stop_price is not None:
            stop_price = _coerce_decimal(self.new_stop_price, field_name="new_stop_price")
            object.__setattr__(self, "new_stop_price", stop_price)

        target_price = self.trade.target_price
        if self.new_target_price is not None:
            target_price = _coerce_decimal(self.new_target_price, field_name="new_target_price")
            object.__setattr__(self, "new_target_price", target_price)

        if self.new_stop_price is None and self.new_target_price is None:
            raise ValueError("trade adjustments require a stop_price and/or target_price change")

        TradeProposal(
            symbol=self.trade.symbol,
            entry_price=self.trade.entry_price,
            stop_price=stop_price,
            target_price=target_price,
        )


@dataclass(frozen=True, slots=True)
class TradeClosedEvent:
    trade: OpenTradeSnapshot
    observed_at: datetime
    close_price: Decimal | float | int | str
    reason: str
    realized_pnl: Decimal | float | int | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        object.__setattr__(self, "close_price", _coerce_decimal(self.close_price, field_name="close_price"))
        cleaned_reason = self.reason.strip()
        if not cleaned_reason:
            raise ValueError("reason must not be empty")
        object.__setattr__(self, "reason", cleaned_reason)
        if self.realized_pnl is not None:
            object.__setattr__(
                self,
                "realized_pnl",
                _coerce_decimal(self.realized_pnl, field_name="realized_pnl", allow_negative=True),
            )


@dataclass(frozen=True, slots=True)
class TelegramButton:
    label: str
    callback_data: str

    def __post_init__(self) -> None:
        cleaned_label = self.label.strip()
        cleaned_callback = self.callback_data.strip()
        if not cleaned_label:
            raise ValueError("button label must not be empty")
        if not cleaned_callback:
            raise ValueError("callback_data must not be empty")
        if len(cleaned_callback.encode("utf-8")) > 64:
            raise ValueError("callback_data must be 64 bytes or fewer")
        object.__setattr__(self, "label", cleaned_label)
        object.__setattr__(self, "callback_data", cleaned_callback)


@dataclass(frozen=True, slots=True)
class RenderedTelegramMessage:
    text: str
    buttons: tuple[TelegramButton, ...] = ()

    def __post_init__(self) -> None:
        cleaned_text = self.text.strip()
        if not cleaned_text:
            raise ValueError("text must not be empty")
        object.__setattr__(self, "text", cleaned_text)
        object.__setattr__(self, "buttons", tuple(self.buttons))

