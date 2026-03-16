from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.alerts.approval_workflow import (
    adjust_trade_stop,
    adjust_trade_target,
    approve_with_defaults,
    close_trade,
)
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.paper.broker import PaperBroker
from app.paper.exits import PaperTradeObservation, ResponsiveExitPolicy
from app.paper.models import PaperExitReason, PaperTradeStatus
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _row() -> CandidateRow:
    observed_at = datetime(2026, 3, 15, 14, 40, tzinfo=UTC)
    return CandidateRow(
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


def _actionable_alert():
    row = _row()
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


def _open_trade(*, broker: PaperBroker | None = None):
    active_broker = broker or PaperBroker()
    decision = approve_with_defaults(_actionable_alert())
    trade = active_broker.open_trade(
        decision,
        trade_id="paper-open-001",
        quantity=400,
    )
    return active_broker, trade


def test_market_update_closes_trade_at_stop_price() -> None:
    broker, trade = _open_trade()

    closed = broker.handle_market_update(
        trade,
        PaperTradeObservation(
            observed_at=trade.opened_at + timedelta(seconds=20),
            high_price="12.52",
            low_price="11.90",
            close_price="12.00",
        ),
    )

    assert closed.status is PaperTradeStatus.CLOSED
    assert closed.close_price == trade.stop_price
    assert closed.exit_reason is PaperExitReason.STOP_HIT


def test_market_update_closes_trade_at_target_price() -> None:
    broker, trade = _open_trade()

    closed = broker.handle_market_update(
        trade,
        PaperTradeObservation(
            observed_at=trade.opened_at + timedelta(seconds=35),
            high_price="13.70",
            low_price="12.30",
            close_price="13.30",
        ),
    )

    assert closed.status is PaperTradeStatus.CLOSED
    assert closed.close_price == trade.target_price
    assert closed.exit_reason is PaperExitReason.TARGET_HIT


def test_market_update_closes_trade_on_weak_follow_through() -> None:
    broker = PaperBroker(
        exit_policy=ResponsiveExitPolicy(
            weak_follow_through_grace_seconds=120,
            min_progress_r_multiple="0.25",
        )
    )
    broker, trade = _open_trade(broker=broker)

    best_price = trade.fill_price + Decimal("0.09")
    close_price = trade.fill_price - Decimal("0.01")
    closed = broker.handle_market_update(
        trade,
        PaperTradeObservation(
            observed_at=trade.opened_at + timedelta(seconds=125),
            high_price=trade.fill_price + Decimal("0.05"),
            low_price=close_price - Decimal("0.03"),
            close_price=close_price,
            best_price_since_entry=best_price,
        ),
    )

    assert closed.status is PaperTradeStatus.CLOSED
    assert closed.close_price == close_price
    assert closed.exit_reason is PaperExitReason.WEAK_FOLLOW_THROUGH


def test_market_update_closes_trade_on_momentum_failure_signal() -> None:
    broker, trade = _open_trade()
    close_price = trade.fill_price - Decimal("0.04")

    closed = broker.handle_market_update(
        trade,
        PaperTradeObservation(
            observed_at=trade.opened_at + timedelta(seconds=50),
            high_price=trade.fill_price + Decimal("0.03"),
            low_price=close_price - Decimal("0.02"),
            close_price=close_price,
            momentum_failed=True,
            momentum_note="lost_vwap_and_20ema",
        ),
    )

    assert closed.status is PaperTradeStatus.CLOSED
    assert closed.close_price == close_price
    assert closed.exit_reason is PaperExitReason.MOMENTUM_FAILURE


def test_operator_can_adjust_stop_and_target_on_open_trade() -> None:
    broker, trade = _open_trade()

    stop_adjusted = broker.apply_open_trade_command(
        trade,
        adjust_trade_stop(
            trade.open_snapshot,
            new_stop_price="12.05",
            decided_at=trade.opened_at + timedelta(seconds=15),
        ),
    )
    fully_adjusted = broker.apply_open_trade_command(
        stop_adjusted,
        adjust_trade_target(
            stop_adjusted.open_snapshot,
            new_target_price="13.90",
            decided_at=trade.opened_at + timedelta(seconds=25),
        ),
    )

    assert fully_adjusted.status is PaperTradeStatus.OPEN
    assert fully_adjusted.stop_price == Decimal("12.05")
    assert fully_adjusted.target_price == Decimal("13.90")


def test_operator_can_close_trade_immediately() -> None:
    broker, trade = _open_trade()

    closed = broker.apply_open_trade_command(
        trade,
        close_trade(
            trade.open_snapshot,
            decided_at=trade.opened_at + timedelta(seconds=45),
        ),
        close_price="12.80",
    )

    assert closed.status is PaperTradeStatus.CLOSED
    assert closed.close_price == Decimal("12.80")
    assert closed.exit_reason is PaperExitReason.MANUAL_CLOSE


def test_manual_close_requires_explicit_close_price() -> None:
    broker, trade = _open_trade()

    with pytest.raises(ValueError, match="close_price"):
        broker.apply_open_trade_command(
            trade,
            close_trade(
                trade.open_snapshot,
                decided_at=trade.opened_at + timedelta(seconds=45),
            ),
        )
