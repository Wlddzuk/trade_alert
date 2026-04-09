from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.providers.models import normalize_symbol

from .models import PreEntryAlert, PreEntryAlertState


class DeliveryOperation(StrEnum):
    SEND_NEW = "send_new"
    SUPPRESS = "suppress"


@dataclass(frozen=True, slots=True)
class DeliveryDecision:
    operation: DeliveryOperation
    alert: PreEntryAlert
    fresh_message_required: bool
    reason: str


class TelegramDeliveryState:
    _MAX_SYMBOLS = 500  # evict oldest entries beyond this threshold

    def __init__(self) -> None:
        self._history: dict[str, list[PreEntryAlertState]] = {}

    @property
    def surfaced_symbols(self) -> frozenset[str]:
        return frozenset(self._history)

    def has_surfaced(self, symbol: str) -> bool:
        return normalize_symbol(symbol) in self._history

    def history_for(self, symbol: str) -> tuple[PreEntryAlertState, ...]:
        return tuple(self._history.get(normalize_symbol(symbol), ()))

    def handle(self, alert: PreEntryAlert) -> DeliveryDecision:
        history = self._history.get(alert.symbol, [])

        if alert.state in {PreEntryAlertState.BLOCKED, PreEntryAlertState.REJECTED} and not history:
            return DeliveryDecision(
                operation=DeliveryOperation.SUPPRESS,
                alert=alert,
                fresh_message_required=False,
                reason="symbol_not_previously_surfaced",
            )

        if history and history[-1] is alert.state:
            return DeliveryDecision(
                operation=DeliveryOperation.SUPPRESS,
                alert=alert,
                fresh_message_required=False,
                reason="duplicate_state",
            )

        history.append(alert.state)
        self._history[alert.symbol] = history

        # Evict oldest symbols if we exceed the cap
        if len(self._history) > self._MAX_SYMBOLS:
            excess = len(self._history) - self._MAX_SYMBOLS
            for old_key in list(self._history)[:excess]:
                del self._history[old_key]

        reason = "first_surface"
        if len(history) > 1:
            previous_state = history[-2]
            if previous_state is PreEntryAlertState.WATCH and alert.state is PreEntryAlertState.ACTIONABLE:
                reason = "trigger_ready_after_watch"
            else:
                reason = f"{previous_state.value}_to_{alert.state.value}"

        return DeliveryDecision(
            operation=DeliveryOperation.SEND_NEW,
            alert=alert,
            fresh_message_required=True,
            reason=reason,
        )

