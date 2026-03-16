from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.alerts.approval_workflow import approve_with_adjustments, approve_with_defaults, reject_entry
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.paper.broker import PaperBroker
from app.paper.models import PaperFillPolicy, PaperTradeStatus
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


def test_open_trade_from_approved_entry_applies_configurable_slippage() -> None:
    decision = approve_with_defaults(_actionable_alert())
    trade = PaperBroker().open_trade(
        decision,
        trade_id="paper-001",
        quantity=500,
    )

    assert trade.status is PaperTradeStatus.OPEN
    assert trade.requested_entry_price == Decimal("12.45")
    assert trade.fill_price == Decimal("12.45") * Decimal("1.0005")
    assert trade.filled_quantity == 500
    assert trade.partial_fill_ratio == Decimal("1")
    assert trade.open_snapshot.quantity == 500


def test_open_trade_supports_adjusted_levels_before_fill() -> None:
    decision = approve_with_adjustments(
        _actionable_alert(),
        stop_price="12.05",
        target_price="13.90",
    )
    trade = PaperBroker().open_trade(
        decision,
        trade_id="paper-002",
        quantity=250,
    )

    assert trade.stop_price == Decimal("12.05")
    assert trade.target_price == Decimal("13.90")


def test_open_trade_rejects_non_approved_decisions() -> None:
    decision = reject_entry(_actionable_alert(), rejection_reason="manual_skip")

    with pytest.raises(ValueError, match="approved entry decision"):
        PaperBroker().open_trade(decision, trade_id="paper-003", quantity=100)


def test_partial_fill_requires_enabled_policy() -> None:
    decision = approve_with_defaults(_actionable_alert())

    with pytest.raises(ValueError, match="partial fills are disabled"):
        PaperBroker().open_trade(
            decision,
            trade_id="paper-004",
            quantity=500,
            partial_fill_ratio="0.5",
        )


def test_partial_fill_extension_point_is_available_when_enabled() -> None:
    decision = approve_with_defaults(_actionable_alert())
    broker = PaperBroker(fill_policy=PaperFillPolicy(slippage_bps_per_side="7", partial_fills_enabled=True))
    trade = broker.open_trade(
        decision,
        trade_id="paper-005",
        quantity=500,
        partial_fill_ratio="0.4",
    )

    assert trade.fill_price == Decimal("12.45") * Decimal("1.0007")
    assert trade.filled_quantity == 200
    assert trade.partial_fill_ratio == Decimal("0.4")
