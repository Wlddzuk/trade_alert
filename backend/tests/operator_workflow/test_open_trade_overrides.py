from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.action_execution import TelegramActionExecutor
from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.api import TelegramCallbackHandler, TelegramRoutes
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
    executor = TelegramActionExecutor(
        registry=registry,
        broker=PaperBroker(),
        trade_id_factory=lambda alert_id: f"paper-{alert_id}",
        entry_quantity=50,
    )
    handler = TelegramCallbackHandler(executor=executor)
    app = create_app(telegram=TelegramRoutes(callback_handler=handler))
    return app, registry


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


def test_trade_stop_override_executes_through_served_callback_path() -> None:
    app, registry = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)
    _post_webhook(
        app,
        {"callback_query": {"id": "cb-open-served-1", "data": f"entry:ap:{alert.alert_id}"}},
    )
    trade_id = f"paper-{alert.alert_id}"

    start_status, start_body = _post_webhook(
        app,
        {
            "callback_query": {
                "id": "cb-stop-served-1",
                "data": f"trade:st:{trade_id}",
                "from": {"id": "served-operator"},
            }
        },
    )
    assert start_status == 200
    assert start_body["status"] == "needs_input"

    apply_status, apply_body = _post_webhook(
        app,
        {
            "message": {
                "chat": {"id": "served-operator"},
                "text": "12.10",
            }
        },
    )
    assert apply_status == 200
    assert apply_body["status"] == "accepted"
    assert "stop updated" in str(apply_body["message"]).lower()
    assert "12.1" in str(apply_body["message"]).lower()


def test_trade_target_override_reports_invalid_and_duplicate_responses_cleanly() -> None:
    app, registry = _app_with_runtime()
    alert = _actionable_alert()
    registry.register_alert(alert)
    _post_webhook(
        app,
        {"callback_query": {"id": "cb-open-served-2", "data": f"entry:ap:{alert.alert_id}"}},
    )
    trade_id = f"paper-{alert.alert_id}"
    start_payload = {
        "callback_query": {
            "id": "cb-target-served-2",
            "data": f"trade:tg:{trade_id}",
            "from": {"id": "served-target-operator"},
        }
    }

    first_status, first_body = _post_webhook(app, start_payload)
    duplicate_status, duplicate_body = _post_webhook(app, start_payload)
    assert first_status == 200
    assert first_body["status"] == "needs_input"
    assert duplicate_status == 200
    assert duplicate_body["status"] == "duplicate"

    invalid_status, invalid_body = _post_webhook(
        app,
        {
            "message": {
                "chat": {"id": "served-target-operator"},
                "text": "abc",
            }
        },
    )
    assert invalid_status == 200
    assert invalid_body["status"] == "invalid"
    assert "target_price requires a decimal price" in str(invalid_body["message"]).lower()

    apply_status, apply_body = _post_webhook(
        app,
        {
            "message": {
                "chat": {"id": "served-target-operator"},
                "text": "14.20",
            }
        },
    )
    assert apply_status == 200
    assert apply_body["status"] == "accepted"
    assert "target updated" in str(apply_body["message"]).lower()
