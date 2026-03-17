from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.alerts.approval_workflow import (
    adjust_trade_target,
    approve_with_defaults,
    close_trade,
    record_entry_decision,
    record_pre_entry_alert,
)
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.audit.lifecycle_log import LifecycleLog
from app.audit.review_service import TradeReviewService
from app.paper.broker import PaperBroker
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def test_trade_review_groups_completed_trades_by_day_with_newest_first_ordering() -> None:
    log = LifecycleLog()
    broker = PaperBroker()
    service = TradeReviewService()

    earlier_day = datetime(2026, 3, 14, 14, 0, tzinfo=UTC)
    later_day = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

    _record_closed_trade(log, broker, "review-day-1", surfaced_at=earlier_day, close_price="13.10")
    _record_closed_trade(log, broker, "review-day-2", surfaced_at=later_day, close_price="13.40")
    _record_closed_trade(log, broker, "review-day-3", surfaced_at=later_day + timedelta(minutes=10), close_price="13.55")

    feed = service.build_completed_trade_feed(log.all_events())

    assert [day.trading_day.isoformat() for day in feed.days] == ["2026-03-15", "2026-03-14"]
    assert [trade.trade_id for trade in feed.days[0].trades] == ["review-day-3", "review-day-2"]
    assert feed.days[0].trade_count == 2
    assert feed.total_trades == 3


def test_trade_review_preserves_raw_lifecycle_events_as_secondary_detail() -> None:
    log = LifecycleLog()
    broker = PaperBroker()
    service = TradeReviewService()

    _record_closed_trade(log, broker, "review-raw-events", surfaced_at=datetime(2026, 3, 15, 14, 0, tzinfo=UTC), close_price="13.40")

    feed = service.build_completed_trade_feed(log.all_events())
    review = feed.days[0].trades[0]

    assert review.entry_decision == "approve_default"
    assert review.operator_commands == ("adjust_target", "close")
    assert tuple(event.event_type.value for event in review.raw_events) == (
        "pre_entry_alert",
        "entry_decision",
        "trade_opened",
        "trade_command",
        "trade_command",
        "trade_closed",
    )


def _record_closed_trade(
    log: LifecycleLog,
    broker: PaperBroker,
    trade_id: str,
    *,
    surfaced_at: datetime,
    close_price: str,
) -> None:
    alert = replace(_actionable_alert(), surfaced_at=surfaced_at, alert_id=None)
    record_pre_entry_alert(log, alert)
    decision = approve_with_defaults(alert, decided_at=surfaced_at + timedelta(seconds=5))
    record_entry_decision(log, decision)
    trade = broker.open_trade(
        decision,
        trade_id=trade_id,
        quantity=300,
        lifecycle_log=log,
    )
    adjusted = broker.apply_open_trade_command(
        trade,
        adjust_trade_target(
            trade.open_snapshot,
            new_target_price="13.90",
            decided_at=trade.opened_at + timedelta(seconds=10),
        ),
        lifecycle_log=log,
    )
    broker.apply_open_trade_command(
        adjusted,
        close_trade(
            adjusted.open_snapshot,
            decided_at=adjusted.opened_at + timedelta(seconds=20),
        ),
        close_price=close_price,
        lifecycle_log=log,
    )


def _actionable_alert():
    observed_at = datetime(2026, 3, 15, 14, 40, tzinfo=UTC)
    row = CandidateRow(
        symbol="AKRX",
        headline="AKRX reclaims VWAP after fresh news",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=observed_at,
        time_since_news_seconds=90.0,
        observed_at=observed_at,
        price=Decimal("12.45"),
        volume=2_100_000,
        average_daily_volume=Decimal("900000"),
        daily_relative_volume=Decimal("4.4"),
        short_term_relative_volume=Decimal("3.1"),
        gap_percent=Decimal("12.0"),
        change_from_prior_close_percent=Decimal("19.0"),
        pullback_from_high_percent=Decimal("4.8"),
        why_surfaced="breaking_news | move=19% | daily_rvol=4.4x",
    )
    projection = StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=90.0,
        ),
        score=97,
        stage_tag=StrategyStageTag.TRIGGER_READY,
        supporting_reasons=("move=19%", "daily_rvol=4.4x", "trigger=15s"),
        primary_invalid_reason=None,
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("12.45"),
            trigger_bar_started_at=row.observed_at,
            bullish_confirmation=True,
        ),
        invalidation=None,
    )
    return project_pre_entry_alert(
        projection,
        TradeProposal(
            symbol="AKRX",
            entry_price="12.45",
            stop_price="11.95",
            target_price="13.60",
        ),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )
