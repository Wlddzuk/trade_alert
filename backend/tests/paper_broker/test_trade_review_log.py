from __future__ import annotations

from datetime import timedelta

from app.alerts.approval_workflow import (
    adjust_trade_target,
    approve_with_defaults,
    close_trade,
    record_entry_decision,
    record_pre_entry_alert,
)
from app.audit.lifecycle_log import LifecycleLog
from app.audit.trade_review import build_trade_review, build_trade_reviews
from app.paper.broker import PaperBroker

from .test_entry_handling import _actionable_alert


def test_trade_review_reconstructs_operator_actions_from_lifecycle_events() -> None:
    log = LifecycleLog()
    alert = _actionable_alert()
    broker = PaperBroker()

    record_pre_entry_alert(log, alert)
    decision = approve_with_defaults(alert)
    record_entry_decision(log, decision)
    trade = broker.open_trade(
        decision,
        trade_id="paper-review-001",
        quantity=400,
        lifecycle_log=log,
    )
    adjusted = broker.apply_open_trade_command(
        trade,
        adjust_trade_target(
            trade.open_snapshot,
            new_target_price="13.90",
            decided_at=trade.opened_at + timedelta(seconds=15),
        ),
        lifecycle_log=log,
    )
    broker.apply_open_trade_command(
        adjusted,
        close_trade(
            adjusted.open_snapshot,
            decided_at=adjusted.opened_at + timedelta(seconds=30),
        ),
        close_price="13.10",
        lifecycle_log=log,
    )

    review = build_trade_review(log.all_events(), "paper-review-001")

    assert review.symbol == "AKRX"
    assert review.entry_decision == "approve_default"
    assert review.operator_commands == ("adjust_target", "close")
    assert review.entry_price is not None
    assert review.close_price is not None
    assert review.exit_reason == "manual_close"
    assert review.realized_pnl is not None


def test_trade_review_can_list_completed_trades_from_the_event_stream() -> None:
    log = LifecycleLog()
    alert = _actionable_alert()
    broker = PaperBroker()
    decision = approve_with_defaults(alert)

    record_pre_entry_alert(log, alert)
    record_entry_decision(log, decision)
    trade = broker.open_trade(
        decision,
        trade_id="paper-review-002",
        quantity=250,
        lifecycle_log=log,
    )
    broker.apply_open_trade_command(
        trade,
        close_trade(
            trade.open_snapshot,
            decided_at=trade.opened_at + timedelta(seconds=20),
        ),
        close_price="12.90",
        lifecycle_log=log,
    )

    reviews = build_trade_reviews(log.all_events())

    assert len(reviews) == 1
    assert reviews[0].trade_id == "paper-review-002"
