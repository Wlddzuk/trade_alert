from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from app.api import DashboardRoutes, TelegramRoutes


class BuySignalApp:
    def __init__(
        self,
        *,
        dashboard: DashboardRoutes | None = None,
        telegram: TelegramRoutes | None = None,
    ) -> None:
        self.dashboard = dashboard or DashboardRoutes()
        self.telegram = telegram or TelegramRoutes()

    async def __call__(
        self,
        scope: dict[str, object],
        receive: Callable[[], Awaitable[dict[str, object]]],
        send: Callable[[dict[str, object]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await _send_json(
                send,
                status_code=500,
                body={
                    "ok": False,
                    "status": "unsupported",
                    "message": "BuySignalApp only supports HTTP scopes.",
                },
            )
            return

        body = await _read_http_body(receive)
        response = self.telegram.handle_http_request(
            method=str(scope.get("method", "GET")),
            path=str(scope.get("path", "")),
            body=body,
        )
        await _send_json(send, status_code=response.status_code, body=response.body)


def create_app(
    *,
    dashboard: DashboardRoutes | None = None,
    telegram: TelegramRoutes | None = None,
) -> BuySignalApp:
    return BuySignalApp(
        dashboard=dashboard,
        telegram=telegram,
    )


app = create_app()


async def _read_http_body(
    receive: Callable[[], Awaitable[dict[str, object]]],
) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        body = message.get("body", b"")
        if isinstance(body, bytes):
            chunks.append(body)
        elif isinstance(body, bytearray):
            chunks.append(bytes(body))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


async def _send_json(
    send: Callable[[dict[str, object]], Awaitable[None]],
    *,
    status_code: int,
    body: dict[str, object],
) -> None:
    encoded = json.dumps(body).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": encoded,
            "more_body": False,
        }
    )
