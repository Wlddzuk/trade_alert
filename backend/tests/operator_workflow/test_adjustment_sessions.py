from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.alert_emission import TelegramAlertEmissionService
from app.alerts.delivery_state import TelegramDeliveryState
from app.alerts.adjustment_sessions import AdjustmentSessionStore
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.alerts.telegram_runtime import TelegramRuntimeDeliveryService
from app.api.telegram_adjustments import TelegramAdjustmentCoordinator, TelegramAdjustmentStatus
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation
from tests.operator_workflow.test_telegram_alert_emission_flow import FakeTelegramTransport, _qualifying_setup


def _actionable_alert(*, observed_at: datetime | None = None):
    observed_at = observed_at or datetime(2026, 3, 15, 14, 40, tzinfo=UTC)
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
        surfaced_at=observed_at,
    )


def _emit_registered_alert(*, symbol: str = "AKRX"):
    registry = TelegramActionRegistry()
    service = TelegramAlertEmissionService(
        delivery_state=TelegramDeliveryState(),
        delivery_service=TelegramRuntimeDeliveryService(FakeTelegramTransport(["success"])),
        registry=registry,
        operator_chat_id="operator-chat",
    )
    outcome = service.emit(_qualifying_setup(symbol=symbol))
    return registry, outcome


def test_adjustment_session_supports_one_sided_edit_then_confirmation() -> None:
    registry, outcome = _emit_registered_alert()
    coordinator = TelegramAdjustmentCoordinator(registry=registry)
    alert = outcome.alert

    start = coordinator.start_entry_adjustment(actor_id="chat-1", alert=alert, observed_at=alert.surfaced_at)
    assert start.status is TelegramAdjustmentStatus.NEEDS_INPUT
    assert "Current stop" in start.response_text

    stop = coordinator.handle_message(
        actor_id="chat-1",
        text="keep",
        observed_at=alert.surfaced_at + timedelta(seconds=5),
    )
    assert stop.status is TelegramAdjustmentStatus.NEEDS_INPUT
    assert "Current target" in stop.response_text

    target = coordinator.handle_message(
        actor_id="chat-1",
        text="13.90",
        observed_at=alert.surfaced_at + timedelta(seconds=10),
    )
    assert target.status is TelegramAdjustmentStatus.NEEDS_INPUT
    assert "Confirm Adjusted Entry" in target.response_text

    confirm = coordinator.handle_message(
        actor_id="chat-1",
        text="confirm",
        observed_at=alert.surfaced_at + timedelta(seconds=15),
    )
    assert confirm.status is TelegramAdjustmentStatus.ACCEPTED
    assert confirm.stop_changed is False
    assert confirm.target_changed is True
    assert confirm.target_price == "13.9"


def test_adjustment_session_can_cancel_before_completion() -> None:
    registry, outcome = _emit_registered_alert()
    coordinator = TelegramAdjustmentCoordinator(registry=registry)
    alert = outcome.alert
    coordinator.start_entry_adjustment(actor_id="chat-1", alert=alert, observed_at=alert.surfaced_at)

    cancelled = coordinator.handle_message(
        actor_id="chat-1",
        text="cancel",
        observed_at=alert.surfaced_at + timedelta(seconds=5),
    )

    assert cancelled.status is TelegramAdjustmentStatus.CANCELLED
    assert "cancelled" in cancelled.response_text.lower()


def test_adjustment_session_expires_after_timeout() -> None:
    registry, outcome = _emit_registered_alert()
    coordinator = TelegramAdjustmentCoordinator(
        registry=registry,
        sessions=AdjustmentSessionStore(timeout=timedelta(seconds=30)),
    )
    alert = outcome.alert
    coordinator.start_entry_adjustment(actor_id="chat-1", alert=alert, observed_at=alert.surfaced_at)

    expired = coordinator.handle_message(
        actor_id="chat-1",
        text="11.90",
        observed_at=alert.surfaced_at + timedelta(seconds=31),
    )

    assert expired.status is TelegramAdjustmentStatus.EXPIRED
    assert "expired" in expired.response_text.lower()
