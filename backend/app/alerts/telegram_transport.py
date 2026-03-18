from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import TelegramButton


class TelegramTransportError(RuntimeError):
    def __init__(self, reason: str, *, retryable: bool = True) -> None:
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise ValueError("reason must not be empty")
        super().__init__(cleaned_reason)
        self.reason = cleaned_reason
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class TelegramTransportRequest:
    chat_id: str
    text: str
    buttons: tuple[TelegramButton, ...] = ()

    def __post_init__(self) -> None:
        cleaned_chat_id = self.chat_id.strip()
        cleaned_text = self.text.strip()
        if not cleaned_chat_id:
            raise ValueError("chat_id must not be empty")
        if not cleaned_text:
            raise ValueError("text must not be empty")
        object.__setattr__(self, "chat_id", cleaned_chat_id)
        object.__setattr__(self, "text", cleaned_text)
        object.__setattr__(self, "buttons", tuple(self.buttons))


@dataclass(frozen=True, slots=True)
class TelegramTransportReceipt:
    delivery_id: str

    def __post_init__(self) -> None:
        cleaned_delivery_id = self.delivery_id.strip()
        if not cleaned_delivery_id:
            raise ValueError("delivery_id must not be empty")
        object.__setattr__(self, "delivery_id", cleaned_delivery_id)


class TelegramTransport(Protocol):
    def send(self, request: TelegramTransportRequest) -> TelegramTransportReceipt:
        ...
