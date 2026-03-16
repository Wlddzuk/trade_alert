from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.alerts.approval_workflow import combine_entry_eligibility, project_trigger_ready_alert
from app.alerts.models import PreEntryAlertState, TradeProposal
from app.providers.models import CatalystTag
from app.risk.models import SessionState, TradeQualitySnapshot
from app.risk.session_guards import evaluate_session_guards
from app.risk.trade_gates import evaluate_trade_gates
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _projection() -> StrategyProjection:
    observed_at = datetime(2026, 3, 15, 14, 20, tzinfo=UTC)
    row = CandidateRow(
        symbol="AKRX",
        headline="AKRX extends VWAP reclaim",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=observed_at,
        time_since_news_seconds=180.0,
        observed_at=observed_at,
        price=Decimal("12.45"),
        volume=2_200_000,
        average_daily_volume=Decimal("900000"),
        daily_relative_volume=Decimal("4.4"),
        short_term_relative_volume=Decimal("3.0"),
        gap_percent=Decimal("12.1"),
        change_from_prior_close_percent=Decimal("18.9"),
        pullback_from_high_percent=Decimal("4.6"),
        why_surfaced="breaking_news | move=18.9% | daily_rvol=4.4x",
    )
    return StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=observed_at,
            first_catalyst_at=observed_at,
            catalyst_age_seconds=180.0,
        ),
        score=96,
        stage_tag=StrategyStageTag.TRIGGER_READY,
        supporting_reasons=("move=18.9%", "daily_rvol=4.4x", "trigger=15s"),
        primary_invalid_reason=None,
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("12.45"),
            trigger_bar_started_at=observed_at,
            bullish_confirmation=True,
        ),
        invalidation=None,
    )


def _proposal() -> TradeProposal:
    return TradeProposal(
        symbol="AKRX",
        entry_price="12.45",
        stop_price="11.95",
        target_price="13.60",
    )


def test_trigger_ready_setup_becomes_actionable_when_all_guards_pass() -> None:
    projection = _projection()
    eligibility = combine_entry_eligibility(
        evaluate_trade_gates(
            _proposal(),
            TradeQualitySnapshot(
                average_daily_volume="900000",
                spread_percent="0.20",
            ),
            account_equity="25000",
        ),
        evaluate_session_guards(
            projection.row.observed_at,
            SessionState(account_equity="25000"),
        ),
    )

    alert = project_trigger_ready_alert(
        projection,
        _proposal(),
        rank=1,
        eligibility=eligibility,
    )

    assert alert.state is PreEntryAlertState.ACTIONABLE
    assert alert.approval_capable is True


def test_trigger_ready_setup_stays_visible_but_blocked_when_session_guard_fails() -> None:
    projection = _projection()
    eligibility = combine_entry_eligibility(
        evaluate_trade_gates(
            _proposal(),
            TradeQualitySnapshot(
                average_daily_volume="900000",
                spread_percent="0.20",
            ),
            account_equity="25000",
        ),
        evaluate_session_guards(
            projection.row.observed_at,
            SessionState(
                account_equity="25000",
                last_loss_at=projection.row.observed_at - timedelta(minutes=5),
                consecutive_losses=1,
            ),
        ),
    )

    alert = project_trigger_ready_alert(
        projection,
        _proposal(),
        rank=1,
        eligibility=eligibility,
    )

    assert alert.state is PreEntryAlertState.BLOCKED
    assert alert.approval_capable is False
    assert alert.status_reason == "cooldown_active"


def test_trigger_ready_setup_is_rejected_when_trade_quality_fails() -> None:
    projection = _projection()
    eligibility = combine_entry_eligibility(
        evaluate_trade_gates(
            _proposal(),
            TradeQualitySnapshot(
                average_daily_volume="900000",
                spread_percent="0.90",
            ),
            account_equity="25000",
        ),
        evaluate_session_guards(
            projection.row.observed_at,
            SessionState(account_equity="25000"),
        ),
    )

    alert = project_trigger_ready_alert(
        projection,
        _proposal(),
        rank=1,
        eligibility=eligibility,
    )

    assert alert.state is PreEntryAlertState.REJECTED
    assert alert.approval_capable is False
    assert alert.status_reason == "spread_too_wide"
