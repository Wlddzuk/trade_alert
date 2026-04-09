from __future__ import annotations

import asyncio
import functools
import json
import urllib.error
import urllib.request

from .telegram_transport import (
    TelegramEditRequest,
    TelegramTransportError,
    TelegramTransportReceipt,
    TelegramTransportRequest,
)

_TELEGRAM_API = "https://api.telegram.org"


class HttpTelegramTransport:
    """Real TelegramTransport that calls the Telegram Bot API via urllib.

    Both ``send`` and ``edit`` are synchronous (urllib). Use the async
    wrappers ``async_send`` / ``async_edit`` from coroutines to avoid
    blocking the event loop.
    """

    def __init__(self, bot_token: str, *, timeout_seconds: float = 10.0) -> None:
        cleaned = bot_token.strip()
        if not cleaned:
            raise ValueError("bot_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._base = f"{_TELEGRAM_API}/bot{cleaned}"
        self._url = f"{self._base}/sendMessage"
        self._timeout = timeout_seconds

    def send(self, request: TelegramTransportRequest) -> TelegramTransportReceipt:
        payload: dict[str, object] = {
            "chat_id": request.chat_id,
            "text": request.text,
            "parse_mode": "HTML",
        }
        if request.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [
                        {"text": btn.label, "callback_data": btn.callback_data}
                        for btn in request.buttons
                    ]
                ],
            }

        data = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self._url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            status = exc.code
            retryable = status == 429 or status >= 500
            try:
                error_body = json.loads(exc.read())
                reason = error_body.get("description", f"HTTP {status}")
            except Exception:
                reason = f"HTTP {status}"
            raise TelegramTransportError(reason, retryable=retryable) from exc
        except urllib.error.URLError as exc:
            raise TelegramTransportError(
                str(exc.reason), retryable=True
            ) from exc
        except TimeoutError as exc:
            raise TelegramTransportError(
                "request timed out", retryable=True
            ) from exc

        if not body.get("ok"):
            raise TelegramTransportError(
                body.get("description", "unknown Telegram API error"),
                retryable=True,
            )

        message_id = str(body["result"]["message_id"])
        return TelegramTransportReceipt(delivery_id=message_id)

    def edit(self, request: TelegramEditRequest) -> None:
        payload: dict[str, object] = {
            "chat_id": request.chat_id,
            "message_id": int(request.message_id),
            "text": request.text,
            "parse_mode": "HTML",
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self._base}/editMessageText",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            status = exc.code
            retryable = status == 429 or status >= 500
            try:
                error_body = json.loads(exc.read())
                reason = error_body.get("description", f"HTTP {status}")
            except Exception:
                reason = f"HTTP {status}"
            raise TelegramTransportError(reason, retryable=retryable) from exc
        except urllib.error.URLError as exc:
            raise TelegramTransportError(
                str(exc.reason), retryable=True
            ) from exc
        except TimeoutError as exc:
            raise TelegramTransportError(
                "request timed out", retryable=True
            ) from exc

        if not body.get("ok"):
            raise TelegramTransportError(
                body.get("description", "unknown Telegram API error"),
                retryable=True,
            )

    # ── Async wrappers (run blocking urllib in a thread) ────────────────────

    async def async_send(self, request: TelegramTransportRequest) -> TelegramTransportReceipt:
        """Non-blocking send — offloads to a thread so the event loop is free."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.send, request))

    async def async_edit(self, request: TelegramEditRequest) -> None:
        """Non-blocking edit — offloads to a thread so the event loop is free."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, functools.partial(self.edit, request))
