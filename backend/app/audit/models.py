from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.providers.models import ensure_utc, normalize_symbol

PayloadValue = str | int | float | bool | Decimal | None


class LifecycleEventType(StrEnum):
    PRE_ENTRY_ALERT = "pre_entry_alert"
    ENTRY_DECISION = "entry_decision"
    TRADE_OPENED = "trade_opened"
    TRADE_COMMAND = "trade_command"
    TRADE_CLOSED = "trade_closed"


def _freeze_payload(payload: dict[str, PayloadValue] | tuple[tuple[str, PayloadValue], ...]) -> tuple[tuple[str, PayloadValue], ...]:
    if isinstance(payload, tuple):
        return tuple(sorted(payload))
    return tuple(sorted(payload.items()))


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    event_type: LifecycleEventType
    occurred_at: datetime
    symbol: str
    trade_id: str | None = None
    alert_id: str | None = None
    payload: tuple[tuple[str, PayloadValue], ...] | dict[str, PayloadValue] = ()
    event_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at, field_name="occurred_at"))
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))

        trade_id = None if self.trade_id is None else self.trade_id.strip()
        if trade_id == "":
            raise ValueError("trade_id must not be empty when provided")
        object.__setattr__(self, "trade_id", trade_id)

        alert_id = None if self.alert_id is None else self.alert_id.strip()
        if alert_id == "":
            raise ValueError("alert_id must not be empty when provided")
        object.__setattr__(self, "alert_id", alert_id)

        frozen_payload = _freeze_payload(self.payload)
        object.__setattr__(self, "payload", frozen_payload)

        event_id = self.event_id
        if event_id is None:
            event_id = (
                f"{self.event_type.value}:{self.symbol}:{int(self.occurred_at.timestamp() * 1_000_000)}:"
                f"{trade_id or alert_id or 'na'}"
            )
        object.__setattr__(self, "event_id", event_id)

    @property
    def payload_map(self) -> dict[str, PayloadValue]:
        return dict(self.payload)
