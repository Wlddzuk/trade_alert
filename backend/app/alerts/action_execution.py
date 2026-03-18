from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Callable

from app.alerts.approval_workflow import (
    EntryDecision,
    OpenTradeCommand,
    approve_with_defaults,
    close_trade,
    reject_entry,
)
from app.audit.lifecycle_log import LifecycleLog, record_entry_decision
from app.paper.broker import PaperBroker
from app.paper.models import PaperTrade

from .action_resolution import (
    ResolutionStatus,
    TelegramActionRegistry,
    TelegramCallbackAction,
    parse_callback_data,
)


class ExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    STALE = "stale"
    INVALID = "invalid"
    NEEDS_INPUT = "needs_input"


@dataclass(frozen=True, slots=True)
class TelegramExecutionResult:
    status: ExecutionStatus
    response_text: str
    decision: EntryDecision | None = None
    command: OpenTradeCommand | None = None
    trade: PaperTrade | None = None


class TelegramActionExecutor:
    def __init__(
        self,
        *,
        registry: TelegramActionRegistry | None = None,
        broker: PaperBroker | None = None,
        lifecycle_log: LifecycleLog | None = None,
        trade_id_factory: Callable[[str], str] | None = None,
        entry_quantity: int = 1,
        close_price_resolver: Callable[[PaperTrade], Decimal] | None = None,
    ) -> None:
        self.registry = registry or TelegramActionRegistry()
        self.broker = broker or PaperBroker()
        self.lifecycle_log = lifecycle_log or LifecycleLog()
        self.trade_id_factory = trade_id_factory or (lambda alert_id: f"trade-{alert_id}")
        self.entry_quantity = entry_quantity
        self.close_price_resolver = close_price_resolver or (lambda trade: trade.fill_price)

    def execute_callback(
        self,
        *,
        callback_query_id: str,
        callback_data: str,
        observed_at: datetime | None = None,
    ) -> TelegramExecutionResult:
        previous_response = self.registry.response_for_callback(callback_query_id)
        if previous_response is not None:
            return TelegramExecutionResult(
                status=ExecutionStatus.DUPLICATE,
                response_text=f"Action already applied. {previous_response}",
            )

        try:
            parsed = parse_callback_data(callback_query_id, callback_data)
        except ValueError as exc:
            response = str(exc)
            self.registry.remember_callback_response(callback_query_id, response)
            return TelegramExecutionResult(
                status=ExecutionStatus.INVALID,
                response_text=response,
            )

        resolved = self.registry.resolve(parsed)
        if resolved.status is ResolutionStatus.UNKNOWN:
            self.registry.remember_callback_response(callback_query_id, resolved.message)
            return TelegramExecutionResult(
                status=ExecutionStatus.INVALID,
                response_text=resolved.message,
            )
        if resolved.status is ResolutionStatus.STALE:
            self.registry.remember_callback_response(callback_query_id, resolved.message)
            return TelegramExecutionResult(
                status=ExecutionStatus.STALE,
                response_text=resolved.message,
                trade=resolved.trade,
            )

        current_time = datetime.now(tz=UTC) if observed_at is None else observed_at.astimezone(UTC)
        if parsed.action is TelegramCallbackAction.APPROVE:
            assert resolved.alert is not None
            decision = approve_with_defaults(resolved.alert, decided_at=current_time)
            record_entry_decision(self.lifecycle_log, decision)
            trade = self.broker.open_trade(
                decision,
                trade_id=self.trade_id_factory(resolved.alert.alert_id),
                quantity=self.entry_quantity,
                opened_at=current_time,
                lifecycle_log=self.lifecycle_log,
            )
            self.registry.mark_alert_terminal(resolved.alert.alert_id, "trade opened")
            self.registry.register_trade(
                trade,
                status=(
                    f"trade open at {trade.fill_price.normalize():f} "
                    f"with stop {trade.stop_price.normalize():f} and target {trade.target_price.normalize():f}"
                ),
            )
            response = (
                f"Entry approved. Current trade state: open at {trade.fill_price.normalize():f} "
                f"with stop {trade.stop_price.normalize():f} and target {trade.target_price.normalize():f}."
            )
            self.registry.remember_callback_response(callback_query_id, response)
            return TelegramExecutionResult(
                status=ExecutionStatus.ACCEPTED,
                response_text=response,
                decision=decision,
                trade=trade,
            )

        if parsed.action is TelegramCallbackAction.REJECT:
            assert resolved.alert is not None
            decision = reject_entry(
                resolved.alert,
                rejection_reason="operator_rejected",
                decided_at=current_time,
            )
            record_entry_decision(self.lifecycle_log, decision)
            self.registry.mark_alert_terminal(resolved.alert.alert_id, "entry rejected")
            response = "Entry rejected. Current alert state: entry rejected."
            self.registry.remember_callback_response(callback_query_id, response)
            return TelegramExecutionResult(
                status=ExecutionStatus.ACCEPTED,
                response_text=response,
                decision=decision,
            )

        if parsed.action is TelegramCallbackAction.CLOSE:
            assert resolved.trade is not None
            command = close_trade(resolved.trade.open_snapshot, decided_at=current_time)
            closed_trade = self.broker.apply_open_trade_command(
                resolved.trade,
                command,
                close_price=self.close_price_resolver(resolved.trade),
                lifecycle_log=self.lifecycle_log,
            )
            self.registry.update_trade(closed_trade, status="trade closed")
            response = "Trade closed. Current trade state: trade closed."
            self.registry.remember_callback_response(callback_query_id, response)
            return TelegramExecutionResult(
                status=ExecutionStatus.ACCEPTED,
                response_text=response,
                command=command,
                trade=closed_trade,
            )

        response = "Action accepted. Follow-up operator input is required to continue."
        self.registry.remember_callback_response(callback_query_id, response)
        return TelegramExecutionResult(
            status=ExecutionStatus.NEEDS_INPUT,
            response_text=response,
        )
