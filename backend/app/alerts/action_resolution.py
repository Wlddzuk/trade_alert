from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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


@dataclass(frozen=True, slots=True)
class PendingTradeOverride:
    actor_id: str
    action: TelegramCallbackAction
    trade_id: str
    started_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", ensure_utc(self.started_at, field_name="started_at"))
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at, field_name="expires_at"))
        cleaned_actor_id = self.actor_id.strip()
        if not cleaned_actor_id:
            raise ValueError("actor_id must not be empty")
        object.__setattr__(self, "actor_id", cleaned_actor_id)


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
    _MAX_ALERTS: int = 500
    _MAX_TRADES: int = 200
    _MAX_CALLBACKS: int = 1000
    _alerts: dict[str, _AlertRecord] = field(default_factory=dict)
    _latest_alert_by_symbol: dict[str, str] = field(default_factory=dict)
    _trades: dict[str, _TradeRecord] = field(default_factory=dict)
    _latest_trade_by_symbol: dict[str, str] = field(default_factory=dict)
    _responses_by_callback_id: dict[str, str] = field(default_factory=dict)
    _pending_trade_overrides: dict[str, PendingTradeOverride] = field(default_factory=dict)

    def register_alert(self, alert: PreEntryAlert) -> None:
        record = _AlertRecord(alert=alert, actionable=alert.approval_capable)
        self._alerts[alert.alert_id] = record
        latest_id = self._latest_alert_by_symbol.get(alert.symbol)
        if latest_id is None:
            self._latest_alert_by_symbol[alert.symbol] = alert.alert_id
        elif alert.surfaced_at >= self._alerts[latest_id].alert.surfaced_at:
            self._latest_alert_by_symbol[alert.symbol] = alert.alert_id
        # Evict oldest non-actionable alerts if over cap
        if len(self._alerts) > self._MAX_ALERTS:
            stale = [k for k, v in self._alerts.items() if not v.actionable]
            for old_key in stale[: len(self._alerts) - self._MAX_ALERTS]:
                del self._alerts[old_key]

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

    def start_trade_override(
        self,
        *,
        actor_id: str,
        action: TelegramCallbackAction,
        trade: PaperTrade,
        observed_at: datetime,
        timeout: timedelta = timedelta(minutes=5),
    ) -> PendingTradeOverride:
        if action not in {TelegramCallbackAction.ADJUST_STOP, TelegramCallbackAction.ADJUST_TARGET}:
            raise ValueError("trade override sessions only support stop/target adjustments")
        current_time = ensure_utc(observed_at, field_name="observed_at")
        session = PendingTradeOverride(
            actor_id=actor_id,
            action=action,
            trade_id=trade.trade_id,
            started_at=current_time,
            expires_at=current_time + timeout,
        )
        self._pending_trade_overrides[session.actor_id] = session
        return session

    def current_trade_override(
        self,
        *,
        actor_id: str,
        observed_at: datetime,
    ) -> PendingTradeOverride | None:
        session = self._pending_trade_overrides.get(actor_id)
        if session is None:
            return None
        current_time = ensure_utc(observed_at, field_name="observed_at")
        if current_time > session.expires_at:
            self._pending_trade_overrides.pop(actor_id, None)
            return None
        return session

    def clear_trade_override(self, actor_id: str) -> None:
        self._pending_trade_overrides.pop(actor_id, None)

    def response_for_callback(self, callback_query_id: str) -> str | None:
        return self._responses_by_callback_id.get(callback_query_id)

    def remember_callback_response(self, callback_query_id: str, response: str) -> None:
        self._responses_by_callback_id[callback_query_id] = response
        # Evict oldest callback responses if over cap
        if len(self._responses_by_callback_id) > self._MAX_CALLBACKS:
            excess = len(self._responses_by_callback_id) - self._MAX_CALLBACKS
            for old_key in list(self._responses_by_callback_id)[:excess]:
                del self._responses_by_callback_id[old_key]

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
            return datetime.now(UTC)
        return ensure_utc(value, field_name="observed_at")
