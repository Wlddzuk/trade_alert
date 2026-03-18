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
        message = update.get("message")
        if callback is None and message is None:
            return TelegramRouteResponse(
                status_code=202,
                body={
                    "ok": True,
                    "status": "ignored",
                    "message": "No Telegram callback or message payload was provided.",
                },
            )

        if message is not None:
            actor_id = _extract_actor_id(message)
            text = str(message.get("text", "")).strip()
            if actor_id is None or not text:
                return TelegramRouteResponse(
                    status_code=400,
                    body={
                        "ok": False,
                        "status": "invalid",
                        "message": "Telegram message payload requires actor identity and text.",
                    },
                )
            result = self.executor.execute_message(
                actor_id=actor_id,
                text=text,
            )
            return TelegramRouteResponse(
                status_code=200,
                body={
                    "ok": result.status is not ExecutionStatus.INVALID,
                    "status": result.status.value,
                    "message": result.response_text,
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
            actor_id=_extract_actor_id(callback),
        )
        return TelegramRouteResponse(
            status_code=200,
            body={
                "ok": result.status is not ExecutionStatus.INVALID,
                "status": result.status.value,
                "message": result.response_text,
            },
        )


def _extract_actor_id(payload: Mapping[str, Any]) -> str | None:
    from_payload = payload.get("from")
    if isinstance(from_payload, Mapping):
        actor = str(from_payload.get("id", "")).strip()
        if actor:
            return actor
    message = payload.get("message")
    if isinstance(message, Mapping):
        chat = message.get("chat")
        if isinstance(chat, Mapping):
            actor = str(chat.get("id", "")).strip()
            if actor:
                return actor
    chat = payload.get("chat")
    if isinstance(chat, Mapping):
        actor = str(chat.get("id", "")).strip()
        if actor:
            return actor
    return None
