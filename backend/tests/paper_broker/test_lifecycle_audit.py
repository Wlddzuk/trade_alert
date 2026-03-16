from __future__ import annotations

from datetime import UTC, timedelta

from app.alerts.approval_workflow import (
    adjust_trade_stop,
    approve_with_defaults,
    record_entry_decision,
    record_pre_entry_alert,
)
from app.audit.lifecycle_log import LifecycleLog
from app.audit.models import LifecycleEventType
from app.paper.broker import PaperBroker
from app.paper.exits import PaperTradeObservation

from .test_entry_handling import _actionable_alert


def test_lifecycle_log_records_phase_four_workflow_as_append_only_events() -> None:
    log = LifecycleLog()
    alert = _actionable_alert()
    broker = PaperBroker()

    record_pre_entry_alert(log, alert)
    decision = approve_with_defaults(alert)
    record_entry_decision(log, decision)
    trade = broker.open_trade(
        decision,
        trade_id="paper-audit-001",
        quantity=400,
        lifecycle_log=log,
    )
    adjusted = broker.apply_open_trade_command(
        trade,
        adjust_trade_stop(
            trade.open_snapshot,
            new_stop_price="12.05",
            decided_at=trade.opened_at + timedelta(seconds=20),
        ),
        lifecycle_log=log,
    )
    broker.handle_market_update(
        adjusted,
        PaperTradeObservation(
            observed_at=trade.opened_at + timedelta(seconds=40),
            high_price="13.75",
            low_price="12.20",
            close_price="13.40",
        ),
        lifecycle_log=log,
    )

    events = log.all_events()

    assert tuple(event.event_type for event in events) == (
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
        LifecycleEventType.TRADE_COMMAND,
        LifecycleEventType.TRADE_CLOSED,
    )
    assert all(event.occurred_at.tzinfo is UTC for event in events)
    assert isinstance(events, tuple)


def test_lifecycle_events_freeze_payloads_for_immutable_review() -> None:
    log = LifecycleLog()
    alert = _actionable_alert()

    event = record_pre_entry_alert(log, alert)

    assert event.payload_map["state"] == "actionable"
    assert isinstance(event.payload, tuple)
