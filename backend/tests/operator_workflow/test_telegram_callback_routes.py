from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.audit.lifecycle_log import LifecycleEventType, LifecycleLog
from app.main import create_telegram_operator_runtime
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation
from tests.operator_workflow.test_telegram_alert_emission_flow import FakeTelegramTransport, _qualifying_setup


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
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport([]),
        operator_chat_id="operator-chat",
    )
    return runtime.app, runtime.registry, runtime.lifecycle_log


def _emit_actionable_alert(*, symbol: str = "AKRX", transport_outcomes: list[str] | None = None):
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport(transport_outcomes or ["success"]),
        operator_chat_id="operator-chat",
    )
    outcome = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(symbol=symbol),))[0]
    return runtime, outcome


def test_app_exposes_a_minimal_telegram_update_surface() -> None:
    app, _, _ = _app_with_runtime()

    response = app.telegram.handle_update({})

    assert response.status_code == 202
    assert response.body["status"] == "ignored"


def test_approve_callback_opens_trade_and_records_lifecycle_events() -> None:
    runtime, outcome = _emit_actionable_alert()
    app = runtime.app

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-approve-1",
                "data": f"entry:ap:{outcome.alert.alert_id}",
            }
        }
    )

    assert outcome.emitted is True
    assert response.status_code == 200
    assert response.body["status"] == "accepted"
    assert "Entry approved" in str(response.body["message"])
    events = runtime.lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]
    assert events[1].alert_id == outcome.alert.alert_id
    assert events[2].alert_id == outcome.alert.alert_id
    assert events[2].trade_id == f"paper-{outcome.alert.alert_id}"


def test_reject_callback_marks_emitted_alert_terminal_without_opening_trade() -> None:
    runtime, outcome = _emit_actionable_alert(symbol="BMEA")

    response = runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-reject-1",
                "data": f"entry:rj:{outcome.alert.alert_id}",
            }
        }
    )

    assert outcome.emitted is True
    assert response.status_code == 200
    assert response.body["status"] == "accepted"
    assert "Entry rejected" in str(response.body["message"])
    events = runtime.lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
    ]
    assert events[1].alert_id == outcome.alert.alert_id
    assert events[1].payload_map["rejection_reason"] == "operator_rejected"


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
    runtime, outcome = _emit_actionable_alert()
    runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-open-1",
                "data": f"entry:ap:{outcome.alert.alert_id}",
            }
        }
    )
    trade_id = f"paper-{outcome.alert.alert_id}"

    response = runtime.app.telegram.handle_update(
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
    runtime, outcome = _emit_actionable_alert()

    response = runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-adjust-1",
                "data": f"entry:ad:{outcome.alert.alert_id}",
                "from": {"id": "operator-0"},
            }
        }
    )

    assert response.status_code == 200
    assert response.body["status"] == "needs_input"
    assert "current stop" in str(response.body["message"]).lower()


def test_adjustment_message_flow_requires_confirmation_before_opening_trade() -> None:
    runtime, outcome = _emit_actionable_alert()

    start = runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-adjust-2",
                "data": f"entry:ad:{outcome.alert.alert_id}",
                "from": {"id": "operator-1"},
            }
        }
    )
    assert start.body["status"] == "needs_input"

    stop = runtime.app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-1"},
                "text": "11.90",
            }
        }
    )
    assert stop.body["status"] == "needs_input"
    assert "current target" in str(stop.body["message"]).lower()

    target = runtime.app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-1"},
                "text": "keep",
            }
        }
    )
    assert target.body["status"] == "needs_input"
    assert "confirm adjusted entry" in str(target.body["message"]).lower()

    confirm = runtime.app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-1"},
                "text": "confirm",
            }
        }
    )
    assert confirm.body["status"] == "accepted"
    assert "adjusted entry confirmed" in str(confirm.body["message"]).lower()
    events = runtime.lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]
    assert events[1].alert_id == outcome.alert.alert_id
    assert events[2].alert_id == outcome.alert.alert_id


def test_adjustment_session_reports_expired_and_stale_failures_clearly() -> None:
    app, registry, _ = _app_with_runtime()
    older = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 40, tzinfo=UTC))
    newer = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 41, tzinfo=UTC))
    registry.register_alert(older)

    app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-adjust-stale",
                "data": f"entry:ad:{older.alert_id}",
                "from": {"id": "operator-2"},
            }
        }
    )

    registry.register_alert(newer)
    stale = app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-2"},
                "text": "11.90",
            }
        }
    )
    assert stale.body["status"] == "needs_input"

    confirm = app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-2"},
                "text": "13.90",
            }
        }
    )
    assert confirm.body["status"] == "needs_input"

    stale_confirm = app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-2"},
                "text": "confirm",
            }
        }
    )
    assert stale_confirm.body["status"] == "stale"
    assert "current alert state" in str(stale_confirm.body["message"]).lower()


def test_trade_override_message_flow_updates_stop_and_target_levels() -> None:
    runtime, outcome = _emit_actionable_alert()
    runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-open-override-1",
                "data": f"entry:ap:{outcome.alert.alert_id}",
            }
        }
    )
    trade_id = f"paper-{outcome.alert.alert_id}"

    start_stop = runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-stop-start-1",
                "data": f"trade:st:{trade_id}",
                "from": {"id": "operator-override"},
            }
        }
    )
    assert start_stop.body["status"] == "needs_input"
    assert "new stop price" in str(start_stop.body["message"]).lower()

    stop_reply = runtime.app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-override"},
                "text": "12.05",
            }
        }
    )
    assert stop_reply.body["status"] == "accepted"
    assert "stop updated" in str(stop_reply.body["message"]).lower()
    assert "12.05" in str(stop_reply.body["message"])

    start_target = runtime.app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-target-start-1",
                "data": f"trade:tg:{trade_id}",
                "from": {"id": "operator-override"},
            }
        }
    )
    assert start_target.body["status"] == "needs_input"
    assert "new target price" in str(start_target.body["message"]).lower()

    target_reply = runtime.app.telegram.handle_update(
        {
            "message": {
                "chat": {"id": "operator-override"},
                "text": "13.9",
            }
        }
    )
    assert target_reply.body["status"] == "accepted"
    assert "target updated" in str(target_reply.body["message"]).lower()
    assert "13.9" in str(target_reply.body["message"]).lower()


def test_trade_override_reports_stale_state_after_trade_closes() -> None:
    app, registry, _ = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)
    app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-open-override-2",
                "data": f"entry:ap:{alert.alert_id}",
            }
        }
    )
    trade_id = f"paper-{alert.alert_id}"
    app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-close-override-2",
                "data": f"trade:cl:{trade_id}",
            }
        }
    )

    response = app.telegram.handle_update(
        {
            "callback_query": {
                "id": "cb-stop-stale-2",
                "data": f"trade:st:{trade_id}",
                "from": {"id": "operator-override-stale"},
            }
        }
    )

    assert response.body["status"] == "stale"
    assert "current trade state" in str(response.body["message"]).lower()
