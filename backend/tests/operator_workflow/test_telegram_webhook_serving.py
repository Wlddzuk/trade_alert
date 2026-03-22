from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.action_resolution import ResolutionStatus, TelegramActionRegistry, parse_callback_data
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.audit.lifecycle_log import LifecycleEventType, LifecycleLog
from app.main import create_telegram_operator_runtime
from app.providers.models import CatalystTag
from app.risk.models import EntryDisposition
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


def _runtime_with_emitted_alert(*, symbol: str = "AKRX"):
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport(["success"]),
        operator_chat_id="operator-chat",
    )
    outcome = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(symbol=symbol),))[0]
    return runtime, outcome


def _post_webhook(app, payload: dict[str, object], path: str = "/telegram/webhook") -> tuple[int, dict[str, object]]:
    return asyncio.run(_asgi_post(app, path=path, payload=payload))


async def _asgi_post(app, *, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode("utf-8")
    sent: list[dict[str, object]] = []
    delivered = False

    async def receive() -> dict[str, object]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
        send,
    )

    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    response_body = next(message["body"] for message in sent if message["type"] == "http.response.body")
    return int(status), json.loads(response_body.decode("utf-8"))


def test_webhook_endpoint_accepts_posted_updates_through_asgi_boundary() -> None:
    app, _, _ = _app_with_runtime()

    status, body = _post_webhook(app, {})

    assert status == 202
    assert body["status"] == "ignored"


def test_webhook_endpoint_reaches_runtime_callback_execution() -> None:
    runtime, outcome = _runtime_with_emitted_alert()

    status, body = _post_webhook(
        runtime.app,
        {
            "callback_query": {
                "id": "cb-served-approve-1",
                "data": f"entry:ap:{outcome.alert.alert_id}",
            }
        },
    )

    assert outcome.emitted is True
    assert status == 200
    assert body["status"] == "accepted"
    assert "Entry approved" in str(body["message"])
    events = runtime.lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]
    assert events[1].alert_id == outcome.alert.alert_id
    assert events[2].alert_id == outcome.alert.alert_id


def test_webhook_endpoint_completes_adjusted_approval_from_emitted_alert_state() -> None:
    runtime, outcome = _runtime_with_emitted_alert(symbol="SCPX")

    start_status, start_body = _post_webhook(
        runtime.app,
        {
            "callback_query": {
                "id": "cb-served-adjust-1",
                "data": f"entry:ad:{outcome.alert.alert_id}",
                "from": {"id": "operator-served"},
            }
        },
    )
    stop_status, stop_body = _post_webhook(
        runtime.app,
        {
            "message": {
                "chat": {"id": "operator-served"},
                "text": "11.90",
            }
        },
    )
    target_status, target_body = _post_webhook(
        runtime.app,
        {
            "message": {
                "chat": {"id": "operator-served"},
                "text": "13.90",
            }
        },
    )
    confirm_status, confirm_body = _post_webhook(
        runtime.app,
        {
            "message": {
                "chat": {"id": "operator-served"},
                "text": "confirm",
            }
        },
    )

    assert start_status == 200
    assert start_body["status"] == "needs_input"
    assert "current stop" in str(start_body["message"]).lower()
    assert stop_status == 200
    assert stop_body["status"] == "needs_input"
    assert "current target" in str(stop_body["message"]).lower()
    assert target_status == 200
    assert target_body["status"] == "needs_input"
    assert "confirm adjusted entry" in str(target_body["message"]).lower()
    assert confirm_status == 200
    assert confirm_body["status"] == "accepted"
    assert "adjusted entry confirmed" in str(confirm_body["message"]).lower()
    events = runtime.lifecycle_log.all_events()
    assert [event.event_type for event in events] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]
    assert events[1].alert_id == outcome.alert.alert_id
    assert events[1].payload_map["proposal_stop_price"] == Decimal("11.90")
    assert events[1].payload_map["proposal_target_price"] == Decimal("13.90")
    assert events[2].alert_id == outcome.alert.alert_id


def test_webhook_endpoint_preserves_stale_and_duplicate_behavior() -> None:
    app, registry, _ = _app_with_runtime()
    older = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 40, tzinfo=UTC))
    newer = _actionable_alert(observed_at=datetime(2026, 3, 15, 14, 41, tzinfo=UTC))
    registry.register_alert(older)
    registry.register_alert(newer)

    stale_status, stale_body = _post_webhook(
        app,
        {
            "callback_query": {
                "id": "cb-served-stale-1",
                "data": f"entry:ap:{older.alert_id}",
            }
        },
    )
    assert stale_status == 200
    assert stale_body["status"] == "stale"
    assert "Current alert state" in str(stale_body["message"])

    duplicate_payload = {
        "callback_query": {
            "id": "cb-served-dup-1",
            "data": f"entry:ap:{newer.alert_id}",
        }
    }
    first_status, first_body = _post_webhook(app, duplicate_payload)
    second_status, second_body = _post_webhook(app, duplicate_payload)
    assert first_status == 200
    assert first_body["status"] == "accepted"
    assert second_status == 200
    assert second_body["status"] == "duplicate"
    assert "already applied" in str(second_body["message"]).lower()


def test_webhook_endpoint_rejects_callbacks_for_failed_or_suppressed_emissions() -> None:
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport(["telegram_timeout", "telegram_timeout", "telegram_timeout"]),
        operator_chat_id="operator-chat",
    )
    failed = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(symbol="RZLV"),))[0]
    suppressed = runtime.feed_service.emit_qualifying_setups(
        (_qualifying_setup(symbol="LTRY", disposition=EntryDisposition.REJECTED),)
    )[0]

    failed_status, failed_body = _post_webhook(
        runtime.app,
        {
            "callback_query": {
                "id": "cb-served-failed-1",
                "data": f"entry:ap:{failed.alert.alert_id}",
            }
        },
    )
    suppressed_status, suppressed_body = _post_webhook(
        runtime.app,
        {
            "callback_query": {
                "id": "cb-served-suppressed-1",
                "data": f"entry:ad:{suppressed.alert.alert_id}",
                "from": {"id": "operator-served"},
            }
        },
    )

    assert failed.failed is True
    assert suppressed.suppressed is True
    assert failed_status == 200
    assert failed_body["status"] == "invalid"
    assert "unknown to the runtime state" in str(failed_body["message"]).lower()
    assert suppressed_status == 200
    assert suppressed_body["status"] == "invalid"
    assert "unknown to the runtime state" in str(suppressed_body["message"]).lower()
    assert (
        runtime.registry.resolve(parse_callback_data("cb-served-check-1", f"entry:ap:{failed.alert.alert_id}")).status
        is ResolutionStatus.UNKNOWN
    )
    assert (
        runtime.registry.resolve(parse_callback_data("cb-served-check-2", f"entry:ad:{suppressed.alert.alert_id}")).status
        is ResolutionStatus.UNKNOWN
    )
