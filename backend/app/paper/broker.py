from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.alerts.approval_workflow import EntryDecision, OpenTradeCommand, OpenTradeCommandAction
from app.risk.models import EntryDisposition, EntryEligibility

from .exits import ExitDecision, PaperTradeObservation, ResponsiveExitPolicy, evaluate_exit
from .models import PaperExitReason, PaperFillPolicy, PaperTrade, PaperTradeStatus


@dataclass(frozen=True, slots=True)
class PaperBroker:
    fill_policy: PaperFillPolicy = PaperFillPolicy()
    exit_policy: ResponsiveExitPolicy = ResponsiveExitPolicy()

    def open_trade(
        self,
        decision: EntryDecision,
        *,
        trade_id: str,
        quantity: int | None = None,
        opened_at: datetime | None = None,
        partial_fill_ratio: Decimal | float | int | str | None = None,
        eligibility: EntryEligibility | None = None,
        lifecycle_log=None,
    ) -> PaperTrade:
        if not decision.approved or decision.proposal is None:
            raise ValueError("paper trades require an approved entry decision")
        if eligibility is not None:
            if eligibility.disposition is not EntryDisposition.ACTIONABLE:
                raise ValueError("paper trades require actionable entry eligibility")
            if quantity is None:
                quantity = eligibility.position_size.quantity
            elif eligibility.position_size is not None and quantity != eligibility.position_size.quantity:
                raise ValueError("quantity must match the approved eligibility sizing")

        if quantity is None or quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        fill_ratio = Decimal("1")
        if partial_fill_ratio is not None:
            fill_ratio = Decimal(str(partial_fill_ratio))
            if not self.fill_policy.partial_fills_enabled and fill_ratio != Decimal("1"):
                raise ValueError("partial fills are disabled in the current fill policy")
            if fill_ratio <= 0 or fill_ratio > 1:
                raise ValueError("partial_fill_ratio must be greater than zero and at most one")

        filled_quantity = quantity if fill_ratio == Decimal("1") else int(quantity * fill_ratio)
        if filled_quantity <= 0:
            raise ValueError("partial fill ratio results in zero filled quantity")

        fill_price = self.fill_policy.apply_entry_slippage(decision.proposal.entry_price)
        trade = PaperTrade(
            trade_id=trade_id,
            symbol=decision.symbol,
            opened_at=opened_at or decision.decided_at,
            requested_entry_price=decision.proposal.entry_price,
            fill_price=fill_price,
            stop_price=decision.proposal.stop_price,
            target_price=decision.proposal.target_price,
            requested_quantity=quantity,
            filled_quantity=filled_quantity,
            partial_fill_ratio=fill_ratio,
        )
        if lifecycle_log is not None:
            from app.audit.lifecycle_log import record_trade_opened

            record_trade_opened(
                lifecycle_log,
                trade,
                alert_id=decision.alert_id,
                decision_action=decision.action.value,
            )
        return trade

    def evaluate_exit(
        self,
        trade: PaperTrade,
        observation: PaperTradeObservation,
    ) -> ExitDecision:
        self._require_open_trade(trade)
        if observation.observed_at < trade.opened_at:
            raise ValueError("trade observations cannot predate the trade open")
        return evaluate_exit(trade, observation, exit_policy=self.exit_policy)

    def handle_market_update(
        self,
        trade: PaperTrade,
        observation: PaperTradeObservation,
        *,
        lifecycle_log=None,
    ) -> PaperTrade:
        decision = self.evaluate_exit(trade, observation)
        if not decision.should_exit:
            return trade
        closed_trade = trade.close(
            closed_at=decision.observed_at,
            close_price=decision.close_price,
            exit_reason=decision.reason,
        )
        if lifecycle_log is not None:
            from app.audit.lifecycle_log import record_trade_closed

            record_trade_closed(lifecycle_log, closed_trade)
        return closed_trade

    def apply_open_trade_command(
        self,
        trade: PaperTrade,
        command: OpenTradeCommand,
        *,
        close_price: Decimal | float | int | str | None = None,
        lifecycle_log=None,
    ) -> PaperTrade:
        self._require_open_trade(trade)
        if command.trade_id != trade.trade_id:
            raise ValueError("trade command must match trade_id")
        if command.symbol != trade.symbol:
            raise ValueError("trade command must match symbol")
        if command.decided_at < trade.opened_at:
            raise ValueError("open-trade commands cannot predate the trade open")

        if command.action is OpenTradeCommandAction.CLOSE:
            if close_price is None:
                raise ValueError("close commands require a close_price")
            closed_trade = trade.close(
                closed_at=command.decided_at,
                close_price=close_price,
                exit_reason=PaperExitReason.MANUAL_CLOSE,
            )
            if lifecycle_log is not None:
                from app.audit.lifecycle_log import record_trade_closed, record_trade_command

                record_trade_command(lifecycle_log, command)
                record_trade_closed(lifecycle_log, closed_trade)
            return closed_trade

        if close_price is not None:
            raise ValueError("close_price is only valid for close commands")
        if command.action is OpenTradeCommandAction.ADJUST_STOP:
            updated_trade = trade.with_levels(stop_price=command.new_stop_price)
            if lifecycle_log is not None:
                from app.audit.lifecycle_log import record_trade_command

                record_trade_command(
                    lifecycle_log,
                    command,
                    stop_price=updated_trade.stop_price,
                )
            return updated_trade
        if command.action is OpenTradeCommandAction.ADJUST_TARGET:
            updated_trade = trade.with_levels(target_price=command.new_target_price)
            if lifecycle_log is not None:
                from app.audit.lifecycle_log import record_trade_command

                record_trade_command(
                    lifecycle_log,
                    command,
                    target_price=updated_trade.target_price,
                )
            return updated_trade
        raise ValueError("unsupported open-trade command")

    @staticmethod
    def _require_open_trade(trade: PaperTrade) -> None:
        if trade.status is not PaperTradeStatus.OPEN:
            raise ValueError("paper broker expects an open trade")
