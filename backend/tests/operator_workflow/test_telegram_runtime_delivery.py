from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.alerts.telegram_renderer import render_pre_entry_alert
from app.alerts.telegram_runtime import TelegramDeliveryRequest, TelegramRuntimeDeliveryService
from app.alerts.telegram_transport import (
    TelegramTransportError,
    TelegramTransportReceipt,
    TelegramTransportRequest,
)
from app.ops.alert_delivery_health import AlertDeliveryHealthService, AlertDeliveryResult, build_alert_delivery_snapshot
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


class FakeTelegramTransport:
    def __init__(self, outcomes: list[str]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[TelegramTransportRequest] = []

    def send(self, request: TelegramTransportRequest) -> TelegramTransportReceipt:
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if outcome == "success":
            return TelegramTransportReceipt(delivery_id=f"message-{len(self.requests)}")
        raise TelegramTransportError(outcome)


def _row(symbol: str = "AKRX") -> CandidateRow:
    observed_at = datetime(2026, 3, 18, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol=symbol,
        headline=f"{symbol} reclaims VWAP on catalyst",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=observed_at,
        time_since_news_seconds=210.0,
        observed_at=observed_at,
        price=Decimal("12.40"),
        volume=1_500_000,
        average_daily_volume=Decimal("420000"),
        daily_relative_volume=Decimal("4.5"),
        short_term_relative_volume=Decimal("2.8"),
        gap_percent=Decimal("12.1"),
        change_from_prior_close_percent=Decimal("17.2"),
        pullback_from_high_percent=Decimal("4.8"),
        why_surfaced="breaking_news | move=17.2% | daily_rvol=4.5x",
    )


def _projection(symbol: str = "AKRX") -> StrategyProjection:
    row = _row(symbol)
    return StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=210.0,
        ),
        score=96,
        stage_tag=StrategyStageTag.TRIGGER_READY,
        supporting_reasons=("move=17.2%", "daily_rvol=4.5x"),
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


def _proposal(symbol: str = "AKRX") -> TradeProposal:
    return TradeProposal(
        symbol=symbol,
        entry_price="12.45",
        stop_price="11.95",
        target_price="13.60",
    )


def _request(symbol: str = "AKRX") -> TelegramDeliveryRequest:
    alert = project_pre_entry_alert(
        _projection(symbol),
        _proposal(symbol),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )
    return TelegramDeliveryRequest(
        chat_id="operator-chat",
        symbol=alert.symbol,
        alert_id=alert.alert_id,
        message=render_pre_entry_alert(alert),
    )


def test_runtime_delivery_uses_rendered_messages_and_succeeds_without_transport_leakage() -> None:
    transport = FakeTelegramTransport(["success"])
    service = TelegramRuntimeDeliveryService(transport)
    request = _request()

    outcome = service.deliver(request, occurred_at=datetime(2026, 3, 18, 14, 0, tzinfo=UTC))

    assert outcome.delivered is True
    assert outcome.receipt is not None
    assert outcome.failure_reason is None
    assert outcome.attempt_count == 1
    assert outcome.attempts[0].result is AlertDeliveryResult.SUCCESS
    assert transport.requests[0].text == request.message.text
    assert transport.requests[0].buttons == request.message.buttons


def test_runtime_delivery_retries_briefly_before_success_and_health_recovers() -> None:
    observed_at = datetime(2026, 3, 18, 14, 5, tzinfo=UTC)
    transport = FakeTelegramTransport(["telegram_timeout", "success"])
    service = TelegramRuntimeDeliveryService(transport, max_attempts=2, retry_delay_seconds=2)

    outcome = service.deliver(_request("BMEA"), occurred_at=observed_at)
    snapshot = build_alert_delivery_snapshot(outcome.attempts, observed_at=observed_at + timedelta(seconds=2))
    report = AlertDeliveryHealthService().build_report(
        outcome.attempts,
        observed_at=observed_at + timedelta(seconds=2),
    )

    assert outcome.delivered is True
    assert [attempt.result for attempt in outcome.attempts] == [
        AlertDeliveryResult.FAILURE,
        AlertDeliveryResult.SUCCESS,
    ]
    assert snapshot.consecutive_failures == 0
    assert snapshot.last_failure_reason is None
    assert snapshot.last_success_at == observed_at + timedelta(seconds=2)
    assert report.snapshot.summary == "Alert delivery recovered after recent failures."
    assert report.recent_failures[0].reason == "telegram_timeout"
    assert report.recent_failures[0].last_success_at is None


def test_runtime_delivery_stops_after_bounded_retry_window() -> None:
    observed_at = datetime(2026, 3, 18, 14, 10, tzinfo=UTC)
    transport = FakeTelegramTransport(["telegram_timeout", "telegram_rate_limited", "telegram_rate_limited"])
    service = TelegramRuntimeDeliveryService(transport, max_attempts=3, retry_delay_seconds=1)

    outcome = service.deliver(_request("RZLV"), occurred_at=observed_at)
    snapshot = build_alert_delivery_snapshot(outcome.attempts, observed_at=observed_at + timedelta(seconds=2))

    assert outcome.delivered is False
    assert outcome.receipt is None
    assert outcome.failure_reason == "telegram_rate_limited"
    assert len(outcome.attempts) == 3
    assert all(attempt.result is AlertDeliveryResult.FAILURE for attempt in outcome.attempts)
    assert snapshot.consecutive_failures == 3
    assert snapshot.last_failure_reason == "telegram_rate_limited"
