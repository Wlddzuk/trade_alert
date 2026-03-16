from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from .models import (
    OpenTradeSnapshot,
    PreEntryAlert,
    PreEntryAlertState,
    RenderedTelegramMessage,
    TelegramButton,
    TradeAdjustedEvent,
    TradeClosedEvent,
    TradeOpenedEvent,
)


def _label(value: str | StrEnum) -> str:
    raw = value.value if isinstance(value, StrEnum) else value
    return raw.replace("_", " ").title()


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _entry_buttons(alert: PreEntryAlert) -> tuple[TelegramButton, ...]:
    if alert.state is not PreEntryAlertState.ACTIONABLE:
        return ()
    return (
        TelegramButton(label="Approve", callback_data=f"entry:ap:{alert.alert_id}"),
        TelegramButton(label="Adjust", callback_data=f"entry:ad:{alert.alert_id}"),
        TelegramButton(label="Reject", callback_data=f"entry:rj:{alert.alert_id}"),
    )


def _trade_buttons(trade: OpenTradeSnapshot) -> tuple[TelegramButton, ...]:
    return (
        TelegramButton(label="Close", callback_data=f"trade:cl:{trade.trade_id}"),
        TelegramButton(label="Adjust Stop", callback_data=f"trade:st:{trade.trade_id}"),
        TelegramButton(label="Adjust Target", callback_data=f"trade:tg:{trade.trade_id}"),
    )


def render_pre_entry_alert(alert: PreEntryAlert) -> RenderedTelegramMessage:
    lines = [
        f"[{_label(alert.state)}] {alert.symbol}",
        f"Catalyst: {_label(alert.projection.row.catalyst_tag)} | {alert.projection.row.headline}",
        f"Setup: {_label(alert.projection.stage_tag)}",
        (
            "Entry / Stop / Target: "
            f"{_format_decimal(alert.proposal.entry_price)} / "
            f"{_format_decimal(alert.proposal.stop_price)} / "
            f"{_format_decimal(alert.proposal.target_price)}"
        ),
        f"Score / Rank: {alert.projection.score} / #{alert.rank}",
    ]

    if alert.projection.supporting_reasons:
        lines.append(f"Context: {', '.join(alert.projection.supporting_reasons)}")

    if alert.display_reason is not None:
        lines.append(f"Status: {alert.display_reason}")

    return RenderedTelegramMessage(text="\n".join(lines), buttons=_entry_buttons(alert))


def render_trade_opened_message(event: TradeOpenedEvent) -> RenderedTelegramMessage:
    lines = [
        f"[Trade Opened] {event.trade.symbol}",
        (
            "Entry / Stop / Target: "
            f"{_format_decimal(event.trade.entry_price)} / "
            f"{_format_decimal(event.trade.stop_price)} / "
            f"{_format_decimal(event.trade.target_price)}"
        ),
    ]
    if event.trade.quantity is not None:
        lines.append(f"Quantity: {event.trade.quantity}")
    if event.note is not None:
        lines.append(f"Note: {event.note}")
    return RenderedTelegramMessage(text="\n".join(lines), buttons=_trade_buttons(event.trade))


def render_trade_adjusted_message(event: TradeAdjustedEvent) -> RenderedTelegramMessage:
    stop_price = event.trade.stop_price if event.new_stop_price is None else event.new_stop_price
    target_price = event.trade.target_price if event.new_target_price is None else event.new_target_price
    lines = [
        f"[Trade Adjusted] {event.trade.symbol}",
        (
            "Entry / Stop / Target: "
            f"{_format_decimal(event.trade.entry_price)} / "
            f"{_format_decimal(stop_price)} / "
            f"{_format_decimal(target_price)}"
        ),
    ]
    if event.note is not None:
        lines.append(f"Note: {event.note}")
    return RenderedTelegramMessage(text="\n".join(lines), buttons=_trade_buttons(event.trade))


def render_trade_closed_message(event: TradeClosedEvent) -> RenderedTelegramMessage:
    lines = [
        f"[Trade Closed] {event.trade.symbol}",
        f"Close Price: {_format_decimal(event.close_price)}",
        f"Reason: {event.reason}",
    ]
    if event.realized_pnl is not None:
        lines.append(f"Realized P&L: {_format_decimal(event.realized_pnl)}")
    return RenderedTelegramMessage(text="\n".join(lines))
