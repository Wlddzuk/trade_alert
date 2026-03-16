from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.providers.models import normalize_symbol

from .models import OpenTradeSnapshot, PreEntryAlert, PreEntryAlertState, TradeProposal


class EntryDecisionAction(StrEnum):
    APPROVE_DEFAULT = "approve_default"
    APPROVE_ADJUSTED = "approve_adjusted"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class EntryDecision:
    action: EntryDecisionAction
    alert_id: str
    symbol: str
    decided_at: datetime
    proposal: TradeProposal | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        object.__setattr__(self, "decided_at", self.decided_at.astimezone(UTC))

        cleaned_alert_id = self.alert_id.strip()
        if not cleaned_alert_id:
            raise ValueError("alert_id must not be empty")
        object.__setattr__(self, "alert_id", cleaned_alert_id)

        reason = None if self.rejection_reason is None else self.rejection_reason.strip()
        if self.action in {EntryDecisionAction.APPROVE_DEFAULT, EntryDecisionAction.APPROVE_ADJUSTED}:
            if self.proposal is None:
                raise ValueError("approved entry decisions require a proposal")
            if self.rejection_reason is not None:
                raise ValueError("approved entry decisions cannot include a rejection_reason")
            if self.proposal.symbol != self.symbol:
                raise ValueError("proposal symbol must match decision symbol")
        elif self.action is EntryDecisionAction.REJECT:
            if self.proposal is not None:
                raise ValueError("rejected entry decisions cannot include a proposal")
            if reason is None:
                raise ValueError("rejected entry decisions require a rejection_reason")

        object.__setattr__(self, "rejection_reason", reason)

    @property
    def approved(self) -> bool:
        return self.action is not EntryDecisionAction.REJECT


class OpenTradeCommandAction(StrEnum):
    CLOSE = "close"
    ADJUST_STOP = "adjust_stop"
    ADJUST_TARGET = "adjust_target"


@dataclass(frozen=True, slots=True)
class OpenTradeCommand:
    action: OpenTradeCommandAction
    trade_id: str
    symbol: str
    decided_at: datetime
    new_stop_price: str | None = None
    new_target_price: str | None = None

    def __post_init__(self) -> None:
        cleaned_trade_id = self.trade_id.strip()
        if not cleaned_trade_id:
            raise ValueError("trade_id must not be empty")
        object.__setattr__(self, "trade_id", cleaned_trade_id)
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        object.__setattr__(self, "decided_at", self.decided_at.astimezone(UTC))

        stop_price = None if self.new_stop_price is None else str(self.new_stop_price).strip()
        target_price = None if self.new_target_price is None else str(self.new_target_price).strip()
        object.__setattr__(self, "new_stop_price", stop_price or None)
        object.__setattr__(self, "new_target_price", target_price or None)

        if self.action is OpenTradeCommandAction.CLOSE:
            if self.new_stop_price is not None or self.new_target_price is not None:
                raise ValueError("close commands cannot include level adjustments")
        elif self.action is OpenTradeCommandAction.ADJUST_STOP:
            if self.new_stop_price is None:
                raise ValueError("adjust_stop commands require a new_stop_price")
            if self.new_target_price is not None:
                raise ValueError("adjust_stop commands cannot include a new_target_price")
        elif self.action is OpenTradeCommandAction.ADJUST_TARGET:
            if self.new_target_price is None:
                raise ValueError("adjust_target commands require a new_target_price")
            if self.new_stop_price is not None:
                raise ValueError("adjust_target commands cannot include a new_stop_price")


def _require_actionable(alert: PreEntryAlert) -> None:
    if alert.state is not PreEntryAlertState.ACTIONABLE:
        raise ValueError("entry decisions require an actionable alert")


def approve_with_defaults(
    alert: PreEntryAlert,
    *,
    decided_at: datetime | None = None,
) -> EntryDecision:
    _require_actionable(alert)
    return EntryDecision(
        action=EntryDecisionAction.APPROVE_DEFAULT,
        alert_id=alert.alert_id,
        symbol=alert.symbol,
        decided_at=decided_at or alert.surfaced_at,
        proposal=alert.proposal,
    )


def approve_with_adjustments(
    alert: PreEntryAlert,
    *,
    stop_price: str | int | float,
    target_price: str | int | float,
    decided_at: datetime | None = None,
) -> EntryDecision:
    _require_actionable(alert)
    adjusted_proposal = TradeProposal(
        symbol=alert.symbol,
        entry_price=alert.proposal.entry_price,
        stop_price=stop_price,
        target_price=target_price,
        thesis=alert.proposal.thesis,
    )
    return EntryDecision(
        action=EntryDecisionAction.APPROVE_ADJUSTED,
        alert_id=alert.alert_id,
        symbol=alert.symbol,
        decided_at=decided_at or alert.surfaced_at,
        proposal=adjusted_proposal,
    )


def reject_entry(
    alert: PreEntryAlert,
    *,
    rejection_reason: str,
    decided_at: datetime | None = None,
) -> EntryDecision:
    _require_actionable(alert)
    return EntryDecision(
        action=EntryDecisionAction.REJECT,
        alert_id=alert.alert_id,
        symbol=alert.symbol,
        decided_at=decided_at or alert.surfaced_at,
        rejection_reason=rejection_reason,
    )


def close_trade(
    trade: OpenTradeSnapshot,
    *,
    decided_at: datetime | None = None,
) -> OpenTradeCommand:
    return OpenTradeCommand(
        action=OpenTradeCommandAction.CLOSE,
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        decided_at=decided_at or trade.opened_at,
    )


def adjust_trade_stop(
    trade: OpenTradeSnapshot,
    *,
    new_stop_price: str | int | float,
    decided_at: datetime | None = None,
) -> OpenTradeCommand:
    TradeProposal(
        symbol=trade.symbol,
        entry_price=trade.entry_price,
        stop_price=new_stop_price,
        target_price=trade.target_price,
    )
    return OpenTradeCommand(
        action=OpenTradeCommandAction.ADJUST_STOP,
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        decided_at=decided_at or trade.opened_at,
        new_stop_price=str(new_stop_price),
    )


def adjust_trade_target(
    trade: OpenTradeSnapshot,
    *,
    new_target_price: str | int | float,
    decided_at: datetime | None = None,
) -> OpenTradeCommand:
    TradeProposal(
        symbol=trade.symbol,
        entry_price=trade.entry_price,
        stop_price=trade.stop_price,
        target_price=new_target_price,
    )
    return OpenTradeCommand(
        action=OpenTradeCommandAction.ADJUST_TARGET,
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        decided_at=decided_at or trade.opened_at,
        new_target_price=str(new_target_price),
    )
