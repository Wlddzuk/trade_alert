from __future__ import annotations

import asyncio
import json

from app.api import DashboardAuthSettings, DashboardRuntimeSnapshotProvider
from app.main import create_app


def test_dashboard_route_dispatch_preserves_telegram_webhook_behavior() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    dashboard_status, dashboard_headers, dashboard_body = _request("GET", "/dashboard", app=app)
    assert dashboard_status == 401
    assert dashboard_headers["content-type"].startswith("text/html")
    assert "Dashboard sign in" in dashboard_body

    telegram_status, telegram_headers, telegram_body = _request(
        "POST",
        "/telegram/webhook",
        app=app,
        payload={},
    )
    assert telegram_status == 202
    assert telegram_headers["content-type"].startswith("application/json")
    assert telegram_body["status"] == "ignored"


def test_root_redirects_to_dashboard_overview() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    status, headers, _ = _request("GET", "/", app=app)

    assert status == 303
    assert headers["location"] == "/dashboard"


def test_dashboard_not_found_returns_helpful_html_page() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    status, headers, body = _request("GET", "/dashboard/mistyped", app=app)

    assert status == 404
    assert headers["content-type"].startswith("text/html")
    assert "Dashboard route not found" in body
    assert "Back to dashboard" in body


def _request(
    method: str,
    path: str,
    *,
    app,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, str], str | dict[str, object]]:
    body = b""
    headers: tuple[tuple[bytes, bytes], ...] = ()
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers = ((b"content-type", b"application/json"),)
    return asyncio.run(_asgi_request(app, method=method, path=path, body=body, headers=headers))


async def _asgi_request(
    app,
    *,
    method: str,
    path: str,
    body: bytes,
    headers: tuple[tuple[bytes, bytes], ...],
) -> tuple[int, dict[str, str], str | dict[str, object]]:
    sent: list[dict[str, object]] = []
    delivered = False

    async def receive() -> dict[str, object]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": list(headers),
        },
        receive,
        send,
    )

    start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = {
        key.decode("utf-8"): value.decode("utf-8")
        for key, value in start.get("headers", [])
    }
    response_body = next(message["body"] for message in sent if message["type"] == "http.response.body")
    if response_headers["content-type"].startswith("application/json"):
        return int(start["status"]), response_headers, json.loads(response_body.decode("utf-8"))
    return int(start["status"]), response_headers, response_body.decode("utf-8")
