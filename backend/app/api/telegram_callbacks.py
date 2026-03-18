from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.alerts.action_execution import ExecutionStatus, TelegramActionExecutor


@dataclass(frozen=True, slots=True)
class TelegramRouteResponse:
    status_code: int
    body: dict[str, object]


class TelegramCallbackHandler:
    def __init__(
        self,
        executor: TelegramActionExecutor | None = None,
    ) -> None:
        self.executor = executor or TelegramActionExecutor()

    def handle_update(self, update: Mapping[str, Any]) -> TelegramRouteResponse:
        callback = update.get("callback_query")
        if callback is None:
            return TelegramRouteResponse(
                status_code=202,
                body={
                    "ok": True,
                    "status": "ignored",
                    "message": "No callback query payload was provided.",
                },
            )

        callback_query_id = str(callback.get("id", "")).strip()
        callback_data = str(callback.get("data", "")).strip()
        if not callback_query_id or not callback_data:
            return TelegramRouteResponse(
                status_code=400,
                body={
                    "ok": False,
                    "status": "invalid",
                    "message": "Telegram callback payload requires both id and data.",
                },
            )

        result = self.executor.execute_callback(
            callback_query_id=callback_query_id,
            callback_data=callback_data,
        )
        return TelegramRouteResponse(
            status_code=200,
            body={
                "ok": result.status is not ExecutionStatus.INVALID,
                "status": result.status.value,
                "message": result.response_text,
            },
        )
