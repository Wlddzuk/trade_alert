from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.delivery_state import DeliveryOperation, TelegramDeliveryState
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _row(symbol: str = "AKRX") -> CandidateRow:
    observed_at = datetime(2026, 3, 15, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol=symbol,
        headline=f"{symbol} holds VWAP after catalyst",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=observed_at,
        time_since_news_seconds=180.0,
        observed_at=observed_at,
        price=Decimal("9.80"),
        volume=980_000,
        average_daily_volume=Decimal("400000"),
        daily_relative_volume=Decimal("3.8"),
        short_term_relative_volume=Decimal("2.4"),
        gap_percent=Decimal("9.2"),
        change_from_prior_close_percent=Decimal("14.3"),
        pullback_from_high_percent=Decimal("4.9"),
        why_surfaced="general | move=14.3% | daily_rvol=3.8x",
    )


def _projection(symbol: str, stage_tag: StrategyStageTag) -> StrategyProjection:
    row = _row(symbol)
    return StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=180.0,
        ),
        score=91,
        stage_tag=stage_tag,
        supporting_reasons=("move=14.3%", "daily_rvol=3.8x"),
        primary_invalid_reason=None,
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("9.84"),
            trigger_bar_started_at=row.observed_at,
            bullish_confirmation=True,
        )
        if stage_tag is StrategyStageTag.TRIGGER_READY
        else None,
        invalidation=None,
    )


def _proposal(symbol: str = "AKRX") -> TradeProposal:
    return TradeProposal(
        symbol=symbol,
        entry_price="9.84",
        stop_price="9.45",
        target_price="10.75",
    )


def test_watch_then_trigger_ready_sends_fresh_actionable_alert() -> None:
    state = TelegramDeliveryState()
    watch_alert = project_pre_entry_alert(
        _projection("AKRX", StrategyStageTag.BUILDING),
        _proposal("AKRX"),
        state=PreEntryAlertState.WATCH,
        rank=2,
    )
    actionable_alert = project_pre_entry_alert(
        _projection("AKRX", StrategyStageTag.TRIGGER_READY),
        _proposal("AKRX"),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )

    first = state.handle(watch_alert)
    second = state.handle(actionable_alert)

    assert first.operation is DeliveryOperation.SEND_NEW
    assert second.operation is DeliveryOperation.SEND_NEW
    assert second.fresh_message_required is True
    assert second.reason == "trigger_ready_after_watch"
    assert state.history_for("AKRX") == (
        PreEntryAlertState.WATCH,
        PreEntryAlertState.ACTIONABLE,
    )


def test_blocked_and_rejected_updates_are_suppressed_for_unsurfaced_symbols() -> None:
    state = TelegramDeliveryState()
    blocked = project_pre_entry_alert(
        _projection("LTRY", StrategyStageTag.TRIGGER_READY),
        _proposal("LTRY"),
        state=PreEntryAlertState.BLOCKED,
        rank=3,
        status_reason="max_open_positions",
    )
    rejected = project_pre_entry_alert(
        _projection("LTRY", StrategyStageTag.TRIGGER_READY),
        _proposal("LTRY"),
        state=PreEntryAlertState.REJECTED,
        rank=3,
        status_reason="spread_too_wide",
    )

    blocked_decision = state.handle(blocked)
    rejected_decision = state.handle(rejected)

    assert blocked_decision.operation is DeliveryOperation.SUPPRESS
    assert rejected_decision.operation is DeliveryOperation.SUPPRESS
    assert state.has_surfaced("LTRY") is False


def test_blocked_update_is_allowed_after_symbol_has_been_surfaced() -> None:
    state = TelegramDeliveryState()
    watch = project_pre_entry_alert(
        _projection("BMEA", StrategyStageTag.BUILDING),
        _proposal("BMEA"),
        state=PreEntryAlertState.WATCH,
        rank=5,
    )
    blocked = project_pre_entry_alert(
        _projection("BMEA", StrategyStageTag.TRIGGER_READY),
        _proposal("BMEA"),
        state=PreEntryAlertState.BLOCKED,
        rank=2,
        status_reason="cooldown_active",
    )

    state.handle(watch)
    decision = state.handle(blocked)

    assert decision.operation is DeliveryOperation.SEND_NEW
    assert decision.reason == "watch_to_blocked"


def test_duplicate_state_is_suppressed_to_keep_telegram_sparse() -> None:
    state = TelegramDeliveryState()
    actionable = project_pre_entry_alert(
        _projection("RZLV", StrategyStageTag.TRIGGER_READY),
        _proposal("RZLV"),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )

    first = state.handle(actionable)
    second = state.handle(actionable)

    assert first.operation is DeliveryOperation.SEND_NEW
    assert second.operation is DeliveryOperation.SUPPRESS
    assert second.reason == "duplicate_state"
