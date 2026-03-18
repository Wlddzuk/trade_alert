from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Callable

from app.alerts.approval_workflow import (
    EntryDecision,
    OpenTradeCommand,
    adjust_trade_stop,
    adjust_trade_target,
    approve_with_adjustments,
    approve_with_defaults,
    close_trade,
    reject_entry,
)
from app.audit.lifecycle_log import LifecycleLog, record_entry_decision
from app.paper.broker import PaperBroker
from app.paper.models import PaperTrade

from .action_resolution import (
    PendingTradeOverride,
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
        from app.api.telegram_adjustments import TelegramAdjustmentCoordinator

        self.adjustments = TelegramAdjustmentCoordinator(registry=self.registry)

    @staticmethod
    def _format_trade_state(trade: PaperTrade) -> str:
        return (
            f"open at {trade.fill_price.normalize():f} "
            f"with stop {trade.stop_price.normalize():f} and target {trade.target_price.normalize():f}"
        )

    @staticmethod
    def _parse_trade_level(text: str, *, field_name: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError(f"{field_name} requires a decimal price.")
        try:
            level = Decimal(cleaned)
        except Exception as exc:  # pragma: no cover - Decimal error type varies
            raise ValueError(f"{field_name} requires a decimal price.") from exc
        if level <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return format(level.normalize(), "f")

    def _apply_trade_override(
        self,
        *,
        session: PendingTradeOverride,
        observed_at: datetime,
        text: str,
    ) -> TelegramExecutionResult:
        resolved = self.registry.resolve(
            parse_callback_data(
                callback_query_id=f"trade-override:{session.trade_id}",
                data=(
                    f"trade:{'st' if session.action is TelegramCallbackAction.ADJUST_STOP else 'tg'}:{session.trade_id}"
                ),
            )
        )
        if resolved.status is not ResolutionStatus.READY or resolved.trade is None:
            self.registry.clear_trade_override(session.actor_id)
            return TelegramExecutionResult(
                status=ExecutionStatus.STALE,
                response_text=resolved.message,
                trade=resolved.trade,
            )

        field_name = "stop_price" if session.action is TelegramCallbackAction.ADJUST_STOP else "target_price"
        try:
            level = self._parse_trade_level(text, field_name=field_name)
        except ValueError as exc:
            return TelegramExecutionResult(
                status=ExecutionStatus.INVALID,
                response_text=str(exc),
                trade=resolved.trade,
            )

        command = (
            adjust_trade_stop(resolved.trade.open_snapshot, new_stop_price=level, decided_at=observed_at)
            if session.action is TelegramCallbackAction.ADJUST_STOP
            else adjust_trade_target(resolved.trade.open_snapshot, new_target_price=level, decided_at=observed_at)
        )
        updated_trade = self.broker.apply_open_trade_command(
            resolved.trade,
            command,
            lifecycle_log=self.lifecycle_log,
        )
        self.registry.update_trade(updated_trade, status=f"trade open {self._format_trade_state(updated_trade)}")
        self.registry.clear_trade_override(session.actor_id)
        action_label = "Stop" if session.action is TelegramCallbackAction.ADJUST_STOP else "Target"
        response = f"{action_label} updated. Current trade state: {self._format_trade_state(updated_trade)}."
        return TelegramExecutionResult(
            status=ExecutionStatus.ACCEPTED,
            response_text=response,
            command=command,
            trade=updated_trade,
        )

    def execute_callback(
        self,
        *,
        callback_query_id: str,
        callback_data: str,
        actor_id: str | None = None,
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

        if parsed.action in {TelegramCallbackAction.ADJUST_STOP, TelegramCallbackAction.ADJUST_TARGET}:
            if actor_id is None:
                response = "Trade override failed. Operator identity is required."
                self.registry.remember_callback_response(callback_query_id, response)
                return TelegramExecutionResult(
                    status=ExecutionStatus.INVALID,
                    response_text=response,
                )
            assert resolved.trade is not None
            self.registry.start_trade_override(
                actor_id=actor_id,
                action=parsed.action,
                trade=resolved.trade,
                observed_at=current_time,
            )
            action_label = "stop" if parsed.action is TelegramCallbackAction.ADJUST_STOP else "target"
            response = (
                f"Reply with the new {action_label} price for {resolved.trade.symbol}. "
                f"Current trade state: {self._format_trade_state(resolved.trade)}."
            )
            self.registry.remember_callback_response(callback_query_id, response)
            return TelegramExecutionResult(
                status=ExecutionStatus.NEEDS_INPUT,
                response_text=response,
                trade=resolved.trade,
            )

        if parsed.action is TelegramCallbackAction.ADJUST:
            if actor_id is None:
                response = "Adjustment start failed. Operator identity is required."
                self.registry.remember_callback_response(callback_query_id, response)
                return TelegramExecutionResult(
                    status=ExecutionStatus.INVALID,
                    response_text=response,
                )
            assert resolved.alert is not None
            adjustment = self.adjustments.start_entry_adjustment(
                actor_id=actor_id,
                alert=resolved.alert,
                observed_at=current_time,
            )
            self.registry.remember_callback_response(callback_query_id, adjustment.response_text)
            return TelegramExecutionResult(
                status=ExecutionStatus.NEEDS_INPUT,
                response_text=adjustment.response_text,
            )

        response = "Action accepted. Follow-up operator input is required to continue."
        self.registry.remember_callback_response(callback_query_id, response)
        return TelegramExecutionResult(
            status=ExecutionStatus.NEEDS_INPUT,
            response_text=response,
        )

    def execute_message(
        self,
        *,
        actor_id: str,
        text: str,
        observed_at: datetime | None = None,
    ) -> TelegramExecutionResult:
        from app.api.telegram_adjustments import TelegramAdjustmentStatus

        current_time = datetime.now(tz=UTC) if observed_at is None else observed_at.astimezone(UTC)
        pending_trade_override = self.registry.current_trade_override(
            actor_id=actor_id,
            observed_at=current_time,
        )
        if pending_trade_override is not None:
            return self._apply_trade_override(
                session=pending_trade_override,
                observed_at=current_time,
                text=text,
            )
        adjustment = self.adjustments.handle_message(
            actor_id=actor_id,
            text=text,
            observed_at=current_time,
        )
        if adjustment.status is TelegramAdjustmentStatus.ACCEPTED:
            assert adjustment.alert is not None
            decision = approve_with_adjustments(
                adjustment.alert,
                stop_price=None if not adjustment.stop_changed else adjustment.stop_price,
                target_price=None if not adjustment.target_changed else adjustment.target_price,
                decided_at=current_time,
            )
            record_entry_decision(self.lifecycle_log, decision)
            trade = self.broker.open_trade(
                decision,
                trade_id=self.trade_id_factory(adjustment.alert.alert_id),
                quantity=self.entry_quantity,
                opened_at=current_time,
                lifecycle_log=self.lifecycle_log,
            )
            self.registry.mark_alert_terminal(adjustment.alert.alert_id, "trade opened")
            self.registry.register_trade(
                trade,
                status=(
                    f"trade open at {trade.fill_price.normalize():f} "
                    f"with stop {trade.stop_price.normalize():f} and target {trade.target_price.normalize():f}"
                ),
            )
            return TelegramExecutionResult(
                status=ExecutionStatus.ACCEPTED,
                response_text=adjustment.response_text,
                decision=decision,
                trade=trade,
            )
        if adjustment.status is TelegramAdjustmentStatus.NEEDS_INPUT:
            return TelegramExecutionResult(
                status=ExecutionStatus.NEEDS_INPUT,
                response_text=adjustment.response_text,
            )
        if adjustment.status in {
            TelegramAdjustmentStatus.CANCELLED,
            TelegramAdjustmentStatus.EXPIRED,
            TelegramAdjustmentStatus.STALE,
        }:
            return TelegramExecutionResult(
                status=ExecutionStatus.STALE,
                response_text=adjustment.response_text,
            )
        return TelegramExecutionResult(
            status=ExecutionStatus.INVALID,
            response_text=adjustment.response_text,
        )
