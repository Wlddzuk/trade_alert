from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.alerts.approval_workflow import (
    EntryDecisionAction,
    OpenTradeCommandAction,
    adjust_trade_stop,
    adjust_trade_target,
    approve_with_adjustments,
    approve_with_defaults,
    close_trade,
    reject_entry,
)
from app.alerts.models import (
    OpenTradeSnapshot,
    PreEntryAlertState,
    TradeProposal,
    project_pre_entry_alert,
)
from app.alerts.telegram_renderer import render_pre_entry_alert
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _row(stage_tag: StrategyStageTag) -> CandidateRow:
    observed_at = datetime(2026, 3, 15, 14, 5, tzinfo=UTC)
    return CandidateRow(
        symbol="OPTT",
        headline="OPTT holds above VWAP after news",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=observed_at,
        time_since_news_seconds=120.0,
        observed_at=observed_at,
        price=Decimal("5.40"),
        volume=1_800_000,
        average_daily_volume=Decimal("750000"),
        daily_relative_volume=Decimal("4.2"),
        short_term_relative_volume=Decimal("2.7"),
        gap_percent=Decimal("10.2"),
        change_from_prior_close_percent=Decimal("16.1"),
        pullback_from_high_percent=Decimal("4.2"),
        why_surfaced="general | move=16.1% | daily_rvol=4.2x",
    )


def _projection(stage_tag: StrategyStageTag) -> StrategyProjection:
    row = _row(stage_tag)
    trigger = None
    if stage_tag is StrategyStageTag.TRIGGER_READY:
        trigger = TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("5.42"),
            trigger_bar_started_at=row.observed_at,
            bullish_confirmation=True,
        )
    return StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=stage_tag is not StrategyStageTag.INVALIDATED,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=120.0,
        ),
        score=93 if trigger else 84,
        stage_tag=stage_tag,
        supporting_reasons=("move=16.1%", "daily_rvol=4.2x"),
        primary_invalid_reason=None,
        trigger_evaluation=trigger,
        invalidation=None,
    )


def _proposal() -> TradeProposal:
    return TradeProposal(
        symbol="OPTT",
        entry_price="5.42",
        stop_price="5.14",
        target_price="5.98",
    )


def _actionable_alert():
    return project_pre_entry_alert(
        _projection(StrategyStageTag.TRIGGER_READY),
        _proposal(),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )


def test_actionable_alert_renders_approve_adjust_and_reject_buttons() -> None:
    rendered = render_pre_entry_alert(_actionable_alert())

    assert [button.label for button in rendered.buttons] == ["Approve", "Adjust", "Reject"]


def test_approve_with_defaults_preserves_alert_entry_levels() -> None:
    decision = approve_with_defaults(_actionable_alert())

    assert decision.action is EntryDecisionAction.APPROVE_DEFAULT
    assert decision.proposal is not None
    assert decision.proposal.entry_price == Decimal("5.42")
    assert decision.proposal.stop_price == Decimal("5.14")
    assert decision.proposal.target_price == Decimal("5.98")


def test_approve_with_adjustments_changes_only_stop_and_target() -> None:
    decision = approve_with_adjustments(
        _actionable_alert(),
        stop_price="5.18",
        target_price="6.05",
    )

    assert decision.action is EntryDecisionAction.APPROVE_ADJUSTED
    assert decision.proposal is not None
    assert decision.proposal.entry_price == Decimal("5.42")
    assert decision.proposal.stop_price == Decimal("5.18")
    assert decision.proposal.target_price == Decimal("6.05")


def test_reject_entry_requires_actionable_alert() -> None:
    watch_alert = project_pre_entry_alert(
        _projection(StrategyStageTag.BUILDING),
        _proposal(),
        state=PreEntryAlertState.WATCH,
        rank=2,
    )

    with pytest.raises(ValueError, match="actionable alert"):
        reject_entry(watch_alert, rejection_reason="manual_skip")


def test_open_trade_commands_cover_close_adjust_stop_and_adjust_target() -> None:
    trade = OpenTradeSnapshot(
        trade_id="trade-123",
        symbol="OPTT",
        opened_at=datetime(2026, 3, 15, 14, 10, tzinfo=UTC),
        entry_price="5.42",
        stop_price="5.14",
        target_price="5.98",
        quantity=250,
    )

    close_command = close_trade(trade)
    stop_command = adjust_trade_stop(trade, new_stop_price="5.20")
    target_command = adjust_trade_target(trade, new_target_price="6.10")

    assert close_command.action is OpenTradeCommandAction.CLOSE
    assert stop_command.action is OpenTradeCommandAction.ADJUST_STOP
    assert stop_command.new_stop_price == "5.20"
    assert target_command.action is OpenTradeCommandAction.ADJUST_TARGET
    assert target_command.new_target_price == "6.10"
