from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.action_execution import TelegramActionExecutor
from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.api import TelegramCallbackHandler, TelegramRoutes
from app.audit.lifecycle_log import LifecycleEventType, LifecycleLog
from app.main import create_app
from app.paper.broker import PaperBroker
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _actionable_alert(*, symbol: str = "AKRX", observed_at: datetime | None = None):
    observed_at = observed_at or datetime(2026, 3, 15, 14, 40, tzinfo=UTC)
    row = CandidateRow(
        symbol=symbol,
        headline=f"{symbol} reclaims VWAP after fresh news",
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
            symbol=symbol,
            entry_price="12.45",
            stop_price="11.95",
            target_price="13.60",
        ),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
        surfaced_at=observed_at,
    )


def _app_with_runtime():
    registry = TelegramActionRegistry()
    lifecycle_log = LifecycleLog()
    executor = TelegramActionExecutor(
        registry=registry,
        broker=PaperBroker(),
        lifecycle_log=lifecycle_log,
        trade_id_factory=lambda alert_id: f"paper-{alert_id}",
        entry_quantity=50,
    )
    handler = TelegramCallbackHandler(executor=executor)
    app = create_app(telegram=TelegramRoutes(callback_handler=handler))
    return app, registry, lifecycle_log


def test_app_exposes_a_minimal_telegram_update_surface() -> None:
    app, _, _ = _app_with_runtime()

    response = app.telegram.handle_update({})

    assert response.status_code == 202
    assert response.body["status"] == "ignored"


def test_approve_callback_opens_trade_and_records_lifecycle_events() -> None:
    app, registry, lifecycle_log = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-approve-1",
                "data": f"entry:ap:{alert.alert_id}",
            }
        }
    )

    assert response.status_code == 200
    assert response.body["status"] == "accepted"
    assert "Entry approved" in str(response.body["message"])
    events = lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]


def test_stale_entry_callback_returns_current_state_feedback() -> None:
    app, registry, _ = _app_with_runtime()
    older = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 40, tzinfo=UTC))
    newer = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 41, tzinfo=UTC))
    registry.register_alert(older)
    registry.register_alert(newer)

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-stale-1",
                "data": f"entry:ap:{older.alert_id}",
            }
        }
    )

    assert response.status_code == 200
    assert response.body["status"] == "stale"
    assert "Current alert state" in str(response.body["message"])


def test_duplicate_callback_query_is_idempotent() -> None:
    app, registry, _ = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)
    update = {
        "callback_query": {
            "id": "cb-dup-1",
            "data": f"entry:ap:{alert.alert_id}",
        }
    }

    first = app.telegram.handle_update(update)
    second = app.telegram.handle_update(update)

    assert first.body["status"] == "accepted"
    assert second.body["status"] == "duplicate"
    assert "already applied" in str(second.body["message"]).lower()


def test_close_trade_callback_reaches_broker_sink_end_to_end() -> None:
    app, registry, _ = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)
    app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-open-1",
                "data": f"entry:ap:{alert.alert_id}",
            }
        }
    )
    trade_id = f"paper-{alert.alert_id}"

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-close-1",
                "data": f"trade:cl:{trade_id}",
            }
        }
    )

    assert response.status_code == 200
    assert response.body["status"] == "accepted"
    assert "trade closed" in str(response.body["message"]).lower()


def test_adjust_callbacks_are_parsed_and_return_follow_up_status() -> None:
    app, registry, _ = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-adjust-1",
                "data": f"entry:ad:{alert.alert_id}",
            }
        }
    )

    assert response.status_code == 200
    assert response.body["status"] == "needs_input"
    assert "follow-up operator input" in str(response.body["message"]).lower()
