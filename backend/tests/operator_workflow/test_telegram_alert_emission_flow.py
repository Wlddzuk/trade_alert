from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.alerts.action_resolution import ResolutionStatus, TelegramActionRegistry, parse_callback_data
from app.alerts.alert_emission import QualifyingSetup, TelegramAlertEmissionService
from app.alerts.delivery_state import DeliveryOperation, TelegramDeliveryState
from app.alerts.models import TradeProposal
from app.alerts.telegram_runtime import TelegramRuntimeDeliveryService
from app.alerts.telegram_transport import (
    TelegramTransportError,
    TelegramTransportReceipt,
    TelegramTransportRequest,
)
from app.audit.lifecycle_log import LifecycleEventType
from app.main import create_telegram_operator_runtime
from app.providers.models import CatalystTag
from app.risk.models import (
    EntryDisposition,
    EntryEligibility,
    PositionSize,
    SessionBlockReason,
    TradeGateReason,
)
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
        if not self._outcomes:
            raise AssertionError("FakeTelegramTransport ran out of configured outcomes")
        outcome = self._outcomes.pop(0)
        if outcome == "success":
            return TelegramTransportReceipt(delivery_id=f"message-{len(self.requests)}")
        raise TelegramTransportError(outcome)


def _projection(symbol: str = "AKRX") -> StrategyProjection:
    observed_at = datetime(2026, 3, 22, 13, 40, tzinfo=UTC)
    row = CandidateRow(
        symbol=symbol,
        headline=f"{symbol} reclaims VWAP after catalyst",
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
    return StrategyProjection(
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


def _proposal(symbol: str = "AKRX") -> TradeProposal:
    return TradeProposal(
        symbol=symbol,
        entry_price="12.45",
        stop_price="11.95",
        target_price="13.60",
    )


def _eligibility(disposition: EntryDisposition = EntryDisposition.ACTIONABLE) -> EntryEligibility:
    if disposition is EntryDisposition.ACTIONABLE:
        return EntryEligibility(
            disposition=disposition,
            position_size=PositionSize(
                quantity=50,
                risk_budget="500",
                risk_per_share="0.50",
                estimated_notional="622.50",
            ),
        )
    if disposition is EntryDisposition.BLOCKED:
        return EntryEligibility(
            disposition=disposition,
            reason=SessionBlockReason.COOLDOWN_ACTIVE,
        )
    return EntryEligibility(
        disposition=disposition,
        reason=TradeGateReason.SPREAD_TOO_WIDE,
    )


def _qualifying_setup(
    *,
    symbol: str = "AKRX",
    disposition: EntryDisposition = EntryDisposition.ACTIONABLE,
) -> QualifyingSetup:
    return QualifyingSetup(
        projection=_projection(symbol),
        proposal=_proposal(symbol),
        rank=1,
        eligibility=_eligibility(disposition),
    )


def _emission_service(
    transport: FakeTelegramTransport,
    *,
    registry: TelegramActionRegistry | None = None,
) -> tuple[TelegramAlertEmissionService, TelegramActionRegistry]:
    registry = registry or TelegramActionRegistry()
    service = TelegramAlertEmissionService(
        delivery_state=TelegramDeliveryState(),
        delivery_service=TelegramRuntimeDeliveryService(transport),
        registry=registry,
        operator_chat_id="operator-chat",
    )
    return service, registry


def test_emitter_sends_trigger_ready_alert_and_registers_it_after_success() -> None:
    transport = FakeTelegramTransport(["success"])
    service, registry = _emission_service(transport)

    result = service.emit(_qualifying_setup())
    resolved = registry.resolve(
        parse_callback_data(
            "cb-approve-1",
            f"entry:ap:{result.alert.alert_id}",
        )
    )

    assert result.emitted is True
    assert result.decision.operation is DeliveryOperation.SEND_NEW
    assert result.registered is True
    assert result.lifecycle_recorded is False
    assert transport.requests[0].chat_id == "operator-chat"
    assert "[Actionable] AKRX" in transport.requests[0].text
    assert resolved.status is ResolutionStatus.READY
    assert resolved.alert is not None
    assert resolved.alert.alert_id == result.alert.alert_id


def test_emitter_suppresses_duplicate_state_without_redelivery_or_registration() -> None:
    transport = FakeTelegramTransport(["success"])
    service, registry = _emission_service(transport)
    first = service.emit(_qualifying_setup())

    duplicate = service.emit(_qualifying_setup())
    resolved = registry.resolve(parse_callback_data("cb-dup-1", f"entry:ap:{duplicate.alert.alert_id}"))

    assert first.emitted is True
    assert duplicate.suppressed is True
    assert duplicate.decision.reason == "duplicate_state"
    assert duplicate.delivery is None
    assert duplicate.registered is False
    assert len(transport.requests) == 1
    assert resolved.status is ResolutionStatus.READY
    assert resolved.alert is not None
    assert resolved.alert.alert_id == first.alert.alert_id


def test_emitter_failed_send_does_not_register_callback_state() -> None:
    transport = FakeTelegramTransport(["telegram_timeout", "telegram_timeout", "telegram_timeout"])
    service, registry = _emission_service(transport)

    result = service.emit(_qualifying_setup(symbol="BMEA"))
    resolved = registry.resolve(parse_callback_data("cb-fail-1", f"entry:ap:{result.alert.alert_id}"))

    assert result.failed is True
    assert result.delivery is not None
    assert result.delivery.failure_reason == "telegram_timeout"
    assert result.registered is False
    assert resolved.status is ResolutionStatus.UNKNOWN


def test_feed_service_emits_real_qualifying_setup_and_records_lifecycle_evidence() -> None:
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport(["success"]),
        operator_chat_id="operator-chat",
    )

    outcomes = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(),))

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.emitted is True
    assert outcome.lifecycle_recorded is True
    assert [event.event_type for event in runtime.lifecycle_log.all_events()] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
    ]


def test_runtime_feed_emission_keeps_alert_available_for_later_operator_approval() -> None:
    transport = FakeTelegramTransport(["success"])
    runtime = create_telegram_operator_runtime(
        transport=transport,
        operator_chat_id="operator-chat",
    )
    outcome = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(),))[0]

    response = runtime.telegram_routes.handle_update(
        {
            "callback_query": {
                "id": "cb-runtime-approve-1",
                "data": f"entry:ap:{outcome.alert.alert_id}",
            }
        }
    )

    assert outcome.emitted is True
    assert response.status_code == 200
    assert response.body["status"] == "accepted"
    assert transport.requests[0].chat_id == "operator-chat"
    assert [event.event_type for event in runtime.lifecycle_log.all_events()] == [
        LifecycleEventType.PRE_ENTRY_ALERT,
        LifecycleEventType.ENTRY_DECISION,
        LifecycleEventType.TRADE_OPENED,
    ]


def test_suppressed_or_failed_paths_do_not_record_false_emitted_alert_evidence() -> None:
    runtime = create_telegram_operator_runtime(
        transport=FakeTelegramTransport(["telegram_timeout", "telegram_timeout", "telegram_timeout"]),
        operator_chat_id="operator-chat",
    )

    failed = runtime.feed_service.emit_qualifying_setups((_qualifying_setup(symbol="RZLV"),))[0]
    suppressed = runtime.feed_service.emit_qualifying_setups(
        (_qualifying_setup(symbol="LTRY", disposition=EntryDisposition.REJECTED),)
    )[0]

    assert failed.failed is True
    assert suppressed.suppressed is True
    assert runtime.lifecycle_log.all_events() == ()
