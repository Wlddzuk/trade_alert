from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.ops.alert_delivery_health import AlertDeliveryAttempt, AlertDeliveryResult

from .models import RenderedTelegramMessage
from .telegram_transport import (
    TelegramTransport,
    TelegramTransportError,
    TelegramTransportReceipt,
    TelegramTransportRequest,
)


@dataclass(frozen=True, slots=True)
class TelegramDeliveryRequest:
    chat_id: str
    symbol: str
    alert_id: str
    message: RenderedTelegramMessage

    def __post_init__(self) -> None:
        cleaned_chat_id = self.chat_id.strip()
        cleaned_symbol = self.symbol.strip().upper()
        cleaned_alert_id = self.alert_id.strip()
        if not cleaned_chat_id:
            raise ValueError("chat_id must not be empty")
        if not cleaned_symbol:
            raise ValueError("symbol must not be empty")
        if not cleaned_alert_id:
            raise ValueError("alert_id must not be empty")
        object.__setattr__(self, "chat_id", cleaned_chat_id)
        object.__setattr__(self, "symbol", cleaned_symbol)
        object.__setattr__(self, "alert_id", cleaned_alert_id)


@dataclass(frozen=True, slots=True)
class TelegramDeliveryOutcome:
    request: TelegramDeliveryRequest
    delivered: bool
    attempts: tuple[AlertDeliveryAttempt, ...]
    receipt: TelegramTransportReceipt | None = None
    failure_reason: str | None = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


class TelegramRuntimeDeliveryService:
    def __init__(
        self,
        transport: TelegramTransport,
        *,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be greater than zero")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be zero or greater")
        self._transport = transport
        self._max_attempts = max_attempts
        self._retry_delay = timedelta(seconds=retry_delay_seconds)

    def deliver(
        self,
        request: TelegramDeliveryRequest,
        *,
        occurred_at: datetime | None = None,
    ) -> TelegramDeliveryOutcome:
        base_time = occurred_at or datetime.now(UTC)
        if base_time.tzinfo is None or base_time.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        attempt_time = base_time.astimezone(UTC)

        attempts: list[AlertDeliveryAttempt] = []
        receipt: TelegramTransportReceipt | None = None
        failure_reason: str | None = None

        transport_request = TelegramTransportRequest(
            chat_id=request.chat_id,
            text=request.message.text,
            buttons=request.message.buttons,
        )

        for attempt_number in range(1, self._max_attempts + 1):
            try:
                receipt = self._transport.send(transport_request)
            except TelegramTransportError as exc:
                failure_reason = exc.reason
                attempts.append(
                    AlertDeliveryAttempt(
                        occurred_at=attempt_time,
                        symbol=request.symbol,
                        alert_id=request.alert_id,
                        result=AlertDeliveryResult.FAILURE,
                        reason=exc.reason,
                    )
                )
                if not exc.retryable or attempt_number >= self._max_attempts:
                    return TelegramDeliveryOutcome(
                        request=request,
                        delivered=False,
                        attempts=tuple(attempts),
                        failure_reason=failure_reason,
                    )
                attempt_time += self._retry_delay
                continue

            attempts.append(
                AlertDeliveryAttempt(
                    occurred_at=attempt_time,
                    symbol=request.symbol,
                    alert_id=request.alert_id,
                    result=AlertDeliveryResult.SUCCESS,
                    reason="delivered",
                )
            )
            return TelegramDeliveryOutcome(
                request=request,
                delivered=True,
                attempts=tuple(attempts),
                receipt=receipt,
            )

        return TelegramDeliveryOutcome(
            request=request,
            delivered=False,
            attempts=tuple(attempts),
            failure_reason=failure_reason,
        )
