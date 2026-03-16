from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import LifecycleEvent, LifecycleEventType

if TYPE_CHECKING:
    from app.alerts.approval_workflow import EntryDecision, OpenTradeCommand
    from app.alerts.models import PreEntryAlert
    from app.paper.models import PaperTrade


class LifecycleLog:
    def __init__(self, events: Iterable[LifecycleEvent] = ()) -> None:
        self._events: list[LifecycleEvent] = list(events)

    def record(self, event: LifecycleEvent) -> LifecycleEvent:
        self._events.append(event)
        return event

    def all_events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self._events)

    def events_for_trade(self, trade_id: str) -> tuple[LifecycleEvent, ...]:
        return tuple(event for event in self._events if event.trade_id == trade_id)

    def events_for_symbol(self, symbol: str) -> tuple[LifecycleEvent, ...]:
        normalized = symbol.strip().upper()
        return tuple(event for event in self._events if event.symbol == normalized)


def record_pre_entry_alert(log: LifecycleLog, alert: "PreEntryAlert") -> LifecycleEvent:
    return log.record(
        LifecycleEvent(
            event_type=LifecycleEventType.PRE_ENTRY_ALERT,
            occurred_at=alert.surfaced_at,
            symbol=alert.symbol,
            alert_id=alert.alert_id,
            payload={
                "state": alert.state.value,
                "rank": alert.rank,
                "score": alert.projection.score,
                "status_reason": alert.status_reason,
            },
        )
    )


def record_entry_decision(log: LifecycleLog, decision: "EntryDecision") -> LifecycleEvent:
    payload = {
        "action": decision.action.value,
        "proposal_entry_price": decision.proposal.entry_price if decision.proposal is not None else None,
        "proposal_stop_price": decision.proposal.stop_price if decision.proposal is not None else None,
        "proposal_target_price": decision.proposal.target_price if decision.proposal is not None else None,
        "rejection_reason": decision.rejection_reason,
    }
    return log.record(
        LifecycleEvent(
            event_type=LifecycleEventType.ENTRY_DECISION,
            occurred_at=decision.decided_at,
            symbol=decision.symbol,
            alert_id=decision.alert_id,
            payload=payload,
        )
    )


def record_trade_opened(
    log: LifecycleLog,
    trade: "PaperTrade",
    *,
    alert_id: str | None = None,
    decision_action: str | None = None,
) -> LifecycleEvent:
    return log.record(
        LifecycleEvent(
            event_type=LifecycleEventType.TRADE_OPENED,
            occurred_at=trade.opened_at,
            symbol=trade.symbol,
            trade_id=trade.trade_id,
            alert_id=alert_id,
            payload={
                "decision_action": decision_action,
                "entry_price": trade.fill_price,
                "requested_entry_price": trade.requested_entry_price,
                "stop_price": trade.stop_price,
                "target_price": trade.target_price,
                "quantity": trade.filled_quantity,
                "partial_fill_ratio": trade.partial_fill_ratio,
            },
        )
    )


def record_trade_command(
    log: LifecycleLog,
    command: "OpenTradeCommand",
    *,
    stop_price: Decimal | None = None,
    target_price: Decimal | None = None,
) -> LifecycleEvent:
    return log.record(
        LifecycleEvent(
            event_type=LifecycleEventType.TRADE_COMMAND,
            occurred_at=command.decided_at,
            symbol=command.symbol,
            trade_id=command.trade_id,
            payload={
                "action": command.action.value,
                "new_stop_price": stop_price,
                "new_target_price": target_price,
            },
        )
    )


def record_trade_closed(log: LifecycleLog, trade: "PaperTrade") -> LifecycleEvent:
    return log.record(
        LifecycleEvent(
            event_type=LifecycleEventType.TRADE_CLOSED,
            occurred_at=trade.closed_at,
            symbol=trade.symbol,
            trade_id=trade.trade_id,
            payload={
                "close_price": trade.close_price,
                "exit_reason": trade.exit_reason.value if trade.exit_reason is not None else None,
                "realized_pnl": trade.realized_pnl,
            },
        )
    )
