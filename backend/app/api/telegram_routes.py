from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .telegram_callbacks import TelegramCallbackHandler, TelegramRouteResponse


class TelegramRoutes:
    def __init__(
        self,
        callback_handler: TelegramCallbackHandler | None = None,
    ) -> None:
        self.callback_handler = callback_handler or TelegramCallbackHandler()

    def handle_update(self, update: Mapping[str, Any]) -> TelegramRouteResponse:
        return self.callback_handler.handle_update(update)
