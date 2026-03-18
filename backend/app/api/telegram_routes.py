from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .telegram_callbacks import TelegramCallbackHandler, TelegramRouteResponse


class TelegramRoutes:
    webhook_path = "/telegram/webhook"

    def __init__(
        self,
        callback_handler: TelegramCallbackHandler | None = None,
    ) -> None:
        self.callback_handler = callback_handler or TelegramCallbackHandler()

    def handle_update(self, update: Mapping[str, Any]) -> TelegramRouteResponse:
        return self.callback_handler.handle_update(update)

    def handle_http_request(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
    ) -> TelegramRouteResponse:
        if path != self.webhook_path:
            return TelegramRouteResponse(
                status_code=404,
                body={
                    "ok": False,
                    "status": "not_found",
                    "message": "Route not found.",
                },
            )
        if method.upper() != "POST":
            return TelegramRouteResponse(
                status_code=405,
                body={
                    "ok": False,
                    "status": "method_not_allowed",
                    "message": "Telegram webhook only accepts POST.",
                },
            )

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return TelegramRouteResponse(
                status_code=400,
                body={
                    "ok": False,
                    "status": "invalid",
                    "message": "Telegram webhook body must be valid JSON.",
                },
            )
        if not isinstance(payload, Mapping):
            return TelegramRouteResponse(
                status_code=400,
                body={
                    "ok": False,
                    "status": "invalid",
                    "message": "Telegram webhook body must decode to an object.",
                },
            )
        return self.handle_update(payload)
