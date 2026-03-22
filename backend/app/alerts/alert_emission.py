from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from app.alerts.approval_workflow import project_trigger_ready_alert
from app.alerts.delivery_state import DeliveryDecision, DeliveryOperation, TelegramDeliveryState
from app.alerts.models import PreEntryAlert, TradeProposal
from app.ops.alert_delivery_health import AlertDeliveryAttempt
from app.alerts.telegram_renderer import render_pre_entry_alert
from app.alerts.telegram_runtime import (
    TelegramDeliveryOutcome,
    TelegramDeliveryRequest,
    TelegramRuntimeDeliveryService,
)
from app.audit.lifecycle_log import LifecycleLog, record_pre_entry_alert
from app.risk.models import EntryEligibility
from app.scanner.strategy_projection import StrategyProjection

from .action_resolution import TelegramActionRegistry


@dataclass(frozen=True, slots=True)
class QualifyingSetup:
    projection: StrategyProjection
    proposal: TradeProposal
    rank: int
    eligibility: EntryEligibility
    surfaced_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AlertEmissionResult:
    alert: PreEntryAlert
    decision: DeliveryDecision
    delivery: TelegramDeliveryOutcome | None
    registered: bool
    lifecycle_recorded: bool

    @property
    def emitted(self) -> bool:
        return self.delivery is not None and self.delivery.delivered

    @property
    def suppressed(self) -> bool:
        return self.decision.operation is DeliveryOperation.SUPPRESS

    @property
    def failed(self) -> bool:
        return self.delivery is not None and not self.delivery.delivered


class TelegramAlertEmissionService:
    def __init__(
        self,
        *,
        delivery_state: TelegramDeliveryState,
        delivery_service: TelegramRuntimeDeliveryService,
        registry: TelegramActionRegistry,
        operator_chat_id: str,
        lifecycle_log: LifecycleLog | None = None,
        delivery_attempt_recorder: Callable[[tuple[AlertDeliveryAttempt, ...]], None] | None = None,
    ) -> None:
        cleaned_chat_id = operator_chat_id.strip()
        if not cleaned_chat_id:
            raise ValueError("operator_chat_id must not be empty")
        self._delivery_state = delivery_state
        self._delivery_service = delivery_service
        self._registry = registry
        self._operator_chat_id = cleaned_chat_id
        self._lifecycle_log = lifecycle_log
        self._delivery_attempt_recorder = delivery_attempt_recorder

    @property
    def operator_chat_id(self) -> str:
        return self._operator_chat_id

    def emit(
        self,
        qualifying_setup: QualifyingSetup,
    ) -> AlertEmissionResult:
        alert = project_trigger_ready_alert(
            qualifying_setup.projection,
            qualifying_setup.proposal,
            rank=qualifying_setup.rank,
            eligibility=qualifying_setup.eligibility,
            surfaced_at=qualifying_setup.surfaced_at,
        )
        decision = self._delivery_state.handle(alert)
        if decision.operation is DeliveryOperation.SUPPRESS:
            return AlertEmissionResult(
                alert=alert,
                decision=decision,
                delivery=None,
                registered=False,
                lifecycle_recorded=False,
            )

        delivery = self._delivery_service.deliver(
            TelegramDeliveryRequest(
                chat_id=self._operator_chat_id,
                symbol=alert.symbol,
                alert_id=alert.alert_id,
                message=render_pre_entry_alert(alert),
            ),
            occurred_at=alert.surfaced_at,
        )
        if self._delivery_attempt_recorder is not None:
            self._delivery_attempt_recorder(delivery.attempts)
        if not delivery.delivered:
            return AlertEmissionResult(
                alert=alert,
                decision=decision,
                delivery=delivery,
                registered=False,
                lifecycle_recorded=False,
            )

        lifecycle_recorded = False
        if self._lifecycle_log is not None:
            record_pre_entry_alert(self._lifecycle_log, alert)
            lifecycle_recorded = True
        self._registry.register_alert(alert)
        return AlertEmissionResult(
            alert=alert,
            decision=decision,
            delivery=delivery,
            registered=True,
            lifecycle_recorded=lifecycle_recorded,
        )
