from __future__ import annotations

import asyncio
import json
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
    app, registry, lifecycle_log = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)

    status, body = _post_webhook(
        app,
        {
            "callback_query": {
                "id": "cb-served-approve-1",
                "data": f"entry:ap:{alert.alert_id}",
            }
        },
    )

    assert status == 200
    assert body["status"] == "accepted"
    assert "Entry approved" in str(body["message"])
    assert [event.event_type for event in lifecycle_log.all_events()] == [
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]


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
