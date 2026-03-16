from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import LifecycleEvent, LifecycleEventType


@dataclass(frozen=True, slots=True)
class TradeReview:
    trade_id: str
    symbol: str
    alert_id: str | None
    surfaced_states: tuple[str, ...]
    entry_decision: str | None
    operator_commands: tuple[str, ...]
    opened_at: datetime | None
    closed_at: datetime | None
    entry_price: Decimal | None
    close_price: Decimal | None
    quantity: int | None
    exit_reason: str | None
    realized_pnl: Decimal | None


def build_trade_review(events: Iterable[LifecycleEvent], trade_id: str) -> TradeReview:
    all_events = tuple(events)
    trade_events = tuple(event for event in all_events if event.trade_id == trade_id)
    if not trade_events:
        raise ValueError("trade review requires lifecycle events for the requested trade_id")

    opened = next((event for event in trade_events if event.event_type is LifecycleEventType.TRADE_OPENED), None)
    closed = next((event for event in trade_events if event.event_type is LifecycleEventType.TRADE_CLOSED), None)
    if opened is None:
        raise ValueError("trade review requires a TRADE_OPENED event")

    alert_id = opened.alert_id
    surfaced_states = tuple(
        event.payload_map["state"]
        for event in all_events
        if event.event_type is LifecycleEventType.PRE_ENTRY_ALERT and event.alert_id == alert_id
    )
    decision = next(
        (
            event
            for event in all_events
            if event.event_type is LifecycleEventType.ENTRY_DECISION and event.alert_id == alert_id
        ),
        None,
    )
    commands = tuple(
        event.payload_map["action"]
        for event in trade_events
        if event.event_type is LifecycleEventType.TRADE_COMMAND
    )

    opened_payload = opened.payload_map
    closed_payload = {} if closed is None else closed.payload_map
    return TradeReview(
        trade_id=trade_id,
        symbol=opened.symbol,
        alert_id=alert_id,
        surfaced_states=surfaced_states,
        entry_decision=None if decision is None else str(decision.payload_map["action"]),
        operator_commands=commands,
        opened_at=opened.occurred_at,
        closed_at=None if closed is None else closed.occurred_at,
        entry_price=None if opened_payload["entry_price"] is None else Decimal(str(opened_payload["entry_price"])),
        close_price=None if closed is None or closed_payload["close_price"] is None else Decimal(str(closed_payload["close_price"])),
        quantity=None if opened_payload["quantity"] is None else int(opened_payload["quantity"]),
        exit_reason=None if closed is None else str(closed_payload["exit_reason"]),
        realized_pnl=None
        if closed is None or closed_payload["realized_pnl"] is None
        else Decimal(str(closed_payload["realized_pnl"])),
    )


def build_trade_reviews(events: Iterable[LifecycleEvent]) -> tuple[TradeReview, ...]:
    grouped: dict[str, list[LifecycleEvent]] = defaultdict(list)
    for event in events:
        if event.trade_id is not None:
            grouped[event.trade_id].append(event)
    return tuple(build_trade_review(events, trade_id) for trade_id in sorted(grouped))
