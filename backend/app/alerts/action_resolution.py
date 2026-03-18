from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.alerts.models import PreEntryAlert
from app.paper.models import PaperTrade, PaperTradeStatus
from app.providers.models import ensure_utc


class TelegramCallbackAction(StrEnum):
    APPROVE = "approve"
    ADJUST = "adjust"
    REJECT = "reject"
    CLOSE = "close"
    ADJUST_STOP = "adjust_stop"
    ADJUST_TARGET = "adjust_target"


_ENTRY_ACTIONS = {
    "ap": TelegramCallbackAction.APPROVE,
    "ad": TelegramCallbackAction.ADJUST,
    "rj": TelegramCallbackAction.REJECT,
}

_TRADE_ACTIONS = {
    "cl": TelegramCallbackAction.CLOSE,
    "st": TelegramCallbackAction.ADJUST_STOP,
    "tg": TelegramCallbackAction.ADJUST_TARGET,
}


@dataclass(frozen=True, slots=True)
class ParsedTelegramCallback:
    callback_query_id: str
    action: TelegramCallbackAction
    target_id: str


class ResolutionStatus(StrEnum):
    READY = "ready"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResolvedTelegramAction:
    status: ResolutionStatus
    callback: ParsedTelegramCallback
    message: str
    alert: PreEntryAlert | None = None
    trade: PaperTrade | None = None


@dataclass(slots=True)
class _AlertRecord:
    alert: PreEntryAlert
    actionable: bool = True
    current_status: str = ""

    def __post_init__(self) -> None:
        if not self.current_status:
            self.current_status = self.alert.state.value.replace("_", " ")


@dataclass(slots=True)
class _TradeRecord:
    trade: PaperTrade
    is_open: bool = True
    current_status: str = ""

    def __post_init__(self) -> None:
        if not self.current_status:
            self.current_status = "open trade"
        self.is_open = self.trade.status is PaperTradeStatus.OPEN


def parse_callback_data(
    callback_query_id: str,
    data: str,
) -> ParsedTelegramCallback:
    cleaned_query_id = callback_query_id.strip()
    if not cleaned_query_id:
        raise ValueError("callback_query_id must not be empty")
    parts = data.strip().split(":", 2)
    if len(parts) != 3:
        raise ValueError("callback_data must use '<scope>:<action>:<id>' format")
    scope, action_code, target_id = parts
    cleaned_target_id = target_id.strip()
    if not cleaned_target_id:
        raise ValueError("callback target id must not be empty")

    if scope == "entry" and action_code in _ENTRY_ACTIONS:
        action = _ENTRY_ACTIONS[action_code]
    elif scope == "trade" and action_code in _TRADE_ACTIONS:
        action = _TRADE_ACTIONS[action_code]
    else:
        raise ValueError("unsupported callback action")

    return ParsedTelegramCallback(
        callback_query_id=cleaned_query_id,
        action=action,
        target_id=cleaned_target_id,
    )


@dataclass(slots=True)
class TelegramActionRegistry:
    _alerts: dict[str, _AlertRecord] = field(default_factory=dict)
    _latest_alert_by_symbol: dict[str, str] = field(default_factory=dict)
    _trades: dict[str, _TradeRecord] = field(default_factory=dict)
    _latest_trade_by_symbol: dict[str, str] = field(default_factory=dict)
    _responses_by_callback_id: dict[str, str] = field(default_factory=dict)

    def register_alert(self, alert: PreEntryAlert) -> None:
        record = _AlertRecord(alert=alert, actionable=alert.approval_capable)
        self._alerts[alert.alert_id] = record
        latest_id = self._latest_alert_by_symbol.get(alert.symbol)
        if latest_id is None:
            self._latest_alert_by_symbol[alert.symbol] = alert.alert_id
            return
        latest_record = self._alerts[latest_id]
        if alert.surfaced_at >= latest_record.alert.surfaced_at:
            self._latest_alert_by_symbol[alert.symbol] = alert.alert_id

    def mark_alert_terminal(self, alert_id: str, status: str) -> None:
        record = self._alerts[alert_id]
        record.actionable = False
        record.current_status = status

    def register_trade(self, trade: PaperTrade, *, status: str | None = None) -> None:
        record = _TradeRecord(trade=trade, current_status=status or "trade open")
        self._trades[trade.trade_id] = record
        self._latest_trade_by_symbol[trade.symbol] = trade.trade_id

    def update_trade(self, trade: PaperTrade, *, status: str) -> None:
        record = self._trades[trade.trade_id]
        record.trade = trade
        record.is_open = trade.status is PaperTradeStatus.OPEN
        record.current_status = status
        if record.is_open:
            self._latest_trade_by_symbol[trade.symbol] = trade.trade_id
        elif self._latest_trade_by_symbol.get(trade.symbol) == trade.trade_id:
            self._latest_trade_by_symbol.pop(trade.symbol, None)

    def response_for_callback(self, callback_query_id: str) -> str | None:
        return self._responses_by_callback_id.get(callback_query_id)

    def remember_callback_response(self, callback_query_id: str, response: str) -> None:
        self._responses_by_callback_id[callback_query_id] = response

    def resolve(self, callback: ParsedTelegramCallback) -> ResolvedTelegramAction:
        if callback.action in {
            TelegramCallbackAction.APPROVE,
            TelegramCallbackAction.ADJUST,
            TelegramCallbackAction.REJECT,
        }:
            return self._resolve_alert(callback)
        return self._resolve_trade(callback)

    def _resolve_alert(self, callback: ParsedTelegramCallback) -> ResolvedTelegramAction:
        record = self._alerts.get(callback.target_id)
        if record is None:
            return ResolvedTelegramAction(
                status=ResolutionStatus.UNKNOWN,
                callback=callback,
                message="Alert is unknown to the runtime state.",
            )

        latest_id = self._latest_alert_by_symbol.get(record.alert.symbol)
        if latest_id != record.alert.alert_id:
            latest = self._alerts[latest_id]
            return ResolvedTelegramAction(
                status=ResolutionStatus.STALE,
                callback=callback,
                message=f"Action no longer valid. Current alert state: {latest.current_status}.",
                alert=latest.alert,
            )
        if not record.actionable:
            return ResolvedTelegramAction(
                status=ResolutionStatus.STALE,
                callback=callback,
                message=f"Action no longer valid. Current alert state: {record.current_status}.",
                alert=record.alert,
            )
        return ResolvedTelegramAction(
            status=ResolutionStatus.READY,
            callback=callback,
            message="Alert is actionable.",
            alert=record.alert,
        )

    def _resolve_trade(self, callback: ParsedTelegramCallback) -> ResolvedTelegramAction:
        record = self._trades.get(callback.target_id)
        if record is None:
            return ResolvedTelegramAction(
                status=ResolutionStatus.UNKNOWN,
                callback=callback,
                message="Trade is unknown to the runtime state.",
            )

        latest_id = self._latest_trade_by_symbol.get(record.trade.symbol)
        if latest_id != record.trade.trade_id or not record.is_open:
            return ResolvedTelegramAction(
                status=ResolutionStatus.STALE,
                callback=callback,
                message=f"Action no longer valid. Current trade state: {record.current_status}.",
                trade=record.trade,
            )
        return ResolvedTelegramAction(
            status=ResolutionStatus.READY,
            callback=callback,
            message="Trade is actionable.",
            trade=record.trade,
        )

    @staticmethod
    def normalize_observed_at(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(tz=ensure_utc(datetime.now().astimezone(), field_name="value").tzinfo)
        return ensure_utc(value, field_name="observed_at")
