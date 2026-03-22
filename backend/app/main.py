from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.alerts.action_execution import TelegramActionExecutor
from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.alert_emission import TelegramAlertEmissionService
from app.alerts.delivery_state import TelegramDeliveryState
from app.alerts.telegram_runtime import TelegramRuntimeDeliveryService
from app.alerts.telegram_transport import TelegramTransport
from app.api import (
    DashboardAuthSettings,
    DashboardRoutes,
    DashboardRuntimeSnapshotProvider,
    TelegramCallbackHandler,
    TelegramRoutes,
)
from app.api.dashboard_runtime import create_default_dashboard_runtime
from app.audit.lifecycle_log import LifecycleLog
from app.paper.broker import PaperBroker
from app.scanner.feed_service import CandidateFeedService


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
    default_dashboard_runtime = create_default_dashboard_runtime()
    return BuySignalApp(
        dashboard=dashboard
        or DashboardRoutes(
            snapshot_provider=dashboard_snapshot_provider or default_dashboard_runtime.snapshot_provider(),
            auth_settings=dashboard_auth_settings,
        ),
        telegram=telegram,
    )


@dataclass(frozen=True, slots=True)
class TelegramOperatorRuntime:
    app: BuySignalApp
    telegram_routes: TelegramRoutes
    callback_handler: TelegramCallbackHandler
    executor: TelegramActionExecutor
    registry: TelegramActionRegistry
    lifecycle_log: LifecycleLog
    delivery_state: TelegramDeliveryState
    delivery_service: TelegramRuntimeDeliveryService
    emission_service: TelegramAlertEmissionService
    feed_service: CandidateFeedService


def create_telegram_operator_runtime(
    *,
    transport: TelegramTransport,
    operator_chat_id: str,
    registry: TelegramActionRegistry | None = None,
    lifecycle_log: LifecycleLog | None = None,
    delivery_state: TelegramDeliveryState | None = None,
    broker: PaperBroker | None = None,
    entry_quantity: int = 50,
) -> TelegramOperatorRuntime:
    registry = registry or TelegramActionRegistry()
    lifecycle_log = lifecycle_log or LifecycleLog()
    delivery_state = delivery_state or TelegramDeliveryState()
    delivery_service = TelegramRuntimeDeliveryService(transport)
    emission_service = TelegramAlertEmissionService(
        delivery_state=delivery_state,
        delivery_service=delivery_service,
        registry=registry,
        operator_chat_id=operator_chat_id,
        lifecycle_log=lifecycle_log,
    )
    feed_service = CandidateFeedService(qualifying_alert_emitter=emission_service)
    executor = TelegramActionExecutor(
        registry=registry,
        broker=broker or PaperBroker(),
        lifecycle_log=lifecycle_log,
        trade_id_factory=lambda alert_id: f"paper-{alert_id}",
        entry_quantity=entry_quantity,
    )
    callback_handler = TelegramCallbackHandler(executor=executor)
    telegram_routes = TelegramRoutes(callback_handler=callback_handler)
    app = create_app(telegram=telegram_routes)
    return TelegramOperatorRuntime(
        app=app,
        telegram_routes=telegram_routes,
        callback_handler=callback_handler,
        executor=executor,
        registry=registry,
        lifecycle_log=lifecycle_log,
        delivery_state=delivery_state,
        delivery_service=delivery_service,
        emission_service=emission_service,
        feed_service=feed_service,
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
