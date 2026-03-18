from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from app.api import DashboardAuthSettings, DashboardRoutes, DashboardRuntimeSnapshotProvider, TelegramRoutes


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
            await _send_bytes(
                send,
                status_code=500,
                body=json.dumps(
                    {
                        "ok": False,
                        "status": "unsupported",
                        "message": "BuySignalApp only supports HTTP scopes.",
                    }
                ).encode("utf-8"),
                content_type=b"application/json",
            )
            return

        body = await _read_http_body(receive)
        method = str(scope.get("method", "GET"))
        path = str(scope.get("path", ""))
        headers = tuple(scope.get("headers", ()))
        if self.dashboard.handles_path(path):
            response = self.dashboard.handle_http_request(
                method=method,
                path=path,
                headers=headers,
                body=body,
            )
            await _send_bytes(
                send,
                status_code=response.status_code,
                body=response.body,
                content_type=response.content_type,
                headers=response.headers,
            )
            return

        response = self.telegram.handle_http_request(method=method, path=path, body=body)
        await _send_json(send, status_code=response.status_code, body=response.body)


def create_app(
    *,
    dashboard: DashboardRoutes | None = None,
    dashboard_snapshot_provider: DashboardRuntimeSnapshotProvider | None = None,
    dashboard_auth_settings: DashboardAuthSettings | None = None,
    telegram: TelegramRoutes | None = None,
) -> BuySignalApp:
    return BuySignalApp(
        dashboard=dashboard
        or DashboardRoutes(
            snapshot_provider=dashboard_snapshot_provider,
            auth_settings=dashboard_auth_settings,
        ),
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
    await _send_bytes(
        send,
        status_code=status_code,
        body=encoded,
        content_type=b"application/json",
    )


async def _send_bytes(
    send: Callable[[dict[str, object]], Awaitable[None]],
    *,
    status_code: int,
    body: bytes,
    content_type: bytes,
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", content_type), *headers],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )
